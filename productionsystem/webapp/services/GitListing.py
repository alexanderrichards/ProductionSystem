"""Github/lab Directory/Tag Listing Service."""
import os
import re
import logging
from distutils.version import StrictVersion  # pylint: disable=import-error, no-name-in-module
import cherrypy
import requests
from enum import Enum
from productionsystem.apache_utils import check_credentials
# gitlab base url: https://lz-git.ua.edu/api/v4


class GitSchema(Enum):
    """
    Git Schema Enum.

    Enum for describing different cloud git hosting APIs.
    """
    GITHUB = 0
    GITLAB = 1


SORT_TYPE_MAPPING = {None: None,
                     'versions': StrictVersion}


class GitListingBase(object):
    """Base Git Listing Service."""

    def __init__(self,
                 api_base_url="https://api.github.com/repos",
                 schema=GitSchema.GITHUB,
                 access_token=''):
        self._logger = logging.getLogger(__name__).getChild(self.__class__.__name__)
        self._api_base_url = api_base_url
        self._schema = schema
        self._token = access_token


@cherrypy.expose
class GitTagListing(GitListingBase):
    """Github/lab Tag listing service."""

    @cherrypy.tools.accept(media='application/json')
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    @check_credentials
    def POST(self, owner, repo):  # pylint: disable=invalid-name
        """HTTP POST request handler."""
        data = cherrypy.request.json
        self._logger.debug("IN POST: owner=%r, repo=%r, data=%r" %
                           (owner, repo, data))
        sort = data.get("sort", False)
        if not isinstance(sort, bool):
            raise cherrypy.HTTPError(400,
                                     "Bad type: sort parameter to be of type bool, got (%r, %s)"
                                     % (sort, type(sort)))
        sort_reversed = data.get("sort-reversed", False)
        if not isinstance(sort_reversed, bool):
            raise cherrypy.HTTPError(400,
                                     "Bad type: sort-reversed parameter to be of type bool, "
                                     "got (%r, %s)" % (sort, type(sort)))
        if sort and sort_reversed:
            raise cherrypy.HTTPError(400,
                                     "Bad request, can't set both sort and sort-reversed "
                                     "parameters to True.")

        sort_type = data.get("sort-type", None)
        if sort_type not in SORT_TYPE_MAPPING:
            raise cherrypy.HTTPError(400,
                                     "Bad type: expected sort-type to be one of %s, "
                                     "got %s" % (SORT_TYPE_MAPPING.keys(),
                                                 sort_type))
        sort_type = SORT_TYPE_MAPPING[sort_type]

        # Schema selection GitSchema.GITHUB is default.
        # ################
        headers = {"Authorization": "token %s" % self._token}
        url = os.path.join(self._api_base_url,
                           owner,
                           repo,
                           "git",
                           "refs",
                           "tags")
        if self._schema == GitSchema.GITLAB:
            headers = {"Private-Token": self._token}
            url = os.path.join(self._api_base_url,
                               "projects",
                               "{owner}%2F{repo}".format(owner=owner, repo=repo),  # %2F = /
                               "repository",
                               "tags")
        # remove attempt at sending Auth token if not present. Will then work for example with
        # public repos.
        if not self._token:
            headers.clear()

        # Call API
        # ########
        self._logger.debug("Using Git API: %s", url)
        # self._logger.debug("->and headers: %s", headers)  # maybe dont disclose token in log.
        with cherrypy.HTTPError.handle(Exception, 500, "Git API call failed"):
            result = requests.get(url, headers=headers)

        status_code = result.status_code
        if status_code != 200:
            raise cherrypy.HTTPError(500, "Git API returned code: %d" % status_code)

        tags_list = result.json()
        tags = (os.path.basename(x['ref']) for x in tags_list)
        if self._schema == GitSchema.GITLAB:
            tags = (x['name'] for x in tags_list)

        output = list(tags)
        if sort or sort_reversed:
            output.sort(reverse=sort_reversed, key=sort_type)
        return output


@cherrypy.expose
class GitDirectoryListing(GitListingBase):
    """Github/lab Directory listing service."""

    def _cp_dispatch(self, vpath):
        if len(vpath) < 2:
            return vpath
        if len(vpath) > 2:
            cherrypy.request.params['path'] = os.path.join(*vpath[2:])
            while len(vpath) > 2:
                vpath.pop()
        cherrypy.request.params['repo'] = vpath.pop()
        cherrypy.request.params['owner'] = vpath.pop()
        return self

    @cherrypy.tools.accept(media='application/json')
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    @check_credentials
    def POST(self, owner, repo, path='/'):  # pylint: disable=invalid-name
        """HTTP POST request handler."""
        data = cherrypy.request.json
        self._logger.debug("IN POST: owner=%r, repo=%r, path=%r, data=%r" %
                           (owner, repo, path, data))

        # Data sanity checking
        # ####################
        with cherrypy.HTTPError.handle(Exception, 400, "Bad RegEx"):
            regex = re.compile(data.get('regex', r'.*'))

        list_type = data.get('type', 'all').lower()
        if list_type not in ("dirs", "files", "all"):
            raise cherrypy.HTTPError(400,
                                     "Bad type: expected one of ('dirs', 'files', 'all'), got %s"
                                     % list_type)

        sort = data.get("sort", False)
        if not isinstance(sort, bool):
            raise cherrypy.HTTPError(400,
                                     "Bad type: sort parameter to be of type bool, got (%r, %s)"
                                     % (sort, type(sort)))
        sort_reversed = data.get("sort-reversed", False)
        if not isinstance(sort_reversed, bool):
            raise cherrypy.HTTPError(400,
                                     "Bad type: sort-reversed parameter to be of type bool, "
                                     "got (%r, %s)" % (sort, type(sort)))
        if sort and sort_reversed:
            raise cherrypy.HTTPError(400,
                                     "Bad request, can't set both sort and sort-reversed "
                                     "parameters to True.")

        sort_type = data.get("sort-type", None)
        if sort_type not in SORT_TYPE_MAPPING:
            raise cherrypy.HTTPError(400,
                                     "Bad type: expected sort-type to be one of %s, "
                                     "got %s" % (SORT_TYPE_MAPPING.keys(),
                                                 sort_type))
        sort_type = SORT_TYPE_MAPPING[sort_type]

        tag = data.get("tag", "master")
        if not isinstance(tag, basestring):
            raise cherrypy.HTTPError(400,
                                     "Bad type: expected tag to be of type str, "
                                     "got (%r, %s)" % (tag, type(tag)))

        # Schema selection GitSchema.GITHUB is default.
        # ################
        params = {"ref": tag}
        headers = {"Authorization": "token %s" % self._token}
        url = os.path.join(self._api_base_url,
                           owner,
                           repo,
                           "contents",
                           path.lstrip('/'))
        if self._schema == GitSchema.GITLAB:
            params.update(path=path)
            headers = {"Private-Token": self._token}
            url = os.path.join(self._api_base_url,
                               "projects",
                               "{owner}%2F{repo}".format(owner=owner, repo=repo),  # %2F = /
                               "repository",
                               "tree")
        # remove attempt at sending Auth token if not present. Will then work for example with
        # public repos.
        if not self._token:
            headers.clear()

        # Call API
        # ########
        self._logger.debug("Using Git API: %s", url)
        self._logger.debug("->with params: %s", params)
        # self._logger.debug("->and headers: %s", headers)  # maybe dont disclose token in log.
        with cherrypy.HTTPError.handle(Exception, 500, "Git API call failed"):
            result = requests.get(url,
                                  params=params,
                                  headers=headers)

        status_code = result.status_code
        if status_code != 200:
            raise cherrypy.HTTPError(500, "Git API returned code: %d" % status_code)

        output = []
        listing = result.json()
        dirs = (x['name'] for x in listing if x['type'] == "dir")
        files = (x['name'] for x in listing if x['type'] == "file")
        if self._schema == GitSchema.GITLAB:
            dirs = (x['name'] for x in listing if x['type'] == "tree")
            files = (x['name'] for x in listing if x['type'] == "blob")
        if list_type in ('dirs', 'all'):
            for dir_ in dirs:
                match = regex.match(dir_)
                if match is not None:
                    output.append(match.group(len(match.groups())))
        if list_type in ('files', 'all'):
            for file_ in files:
                match = regex.match(file_)
                if match is not None:
                    output.append(match.group())

        if sort or sort_reversed:
            output.sort(reverse=sort_reversed, key=sort_type)
        return output
