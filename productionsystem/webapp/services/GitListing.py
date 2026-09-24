"""
Github/lab Directory/Tag Listing Service.
"""
from __future__ import annotations

import logging
import os
import re
from enum import Enum

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException
from git import InvalidGitRepositoryError, NoSuchPathError, Repo
from packaging.version import Version

from productionsystem.apache_utils import get_verified_user
from ._http import http_error_handle

# gitlab base url: https://lz-git.ua.edu/api/v4


class GitSchema(Enum):
    """
    Git Schema Enum.

    Enum for describing different cloud git hosting APIs.
    """

    GITHUB = 0
    GITLAB = 1
    LOCAL = 2


SORT_TYPE_MAPPING = {None: None,
                     'versions': Version}


class GitListingBase(object):
    """
    Base Git Listing Service.
    """
    def __init__(self,
                 api_base_url="https://api.github.com/repos",
                 schema=GitSchema.GITHUB,
                 access_token=''):
        """
        Initialise.

        Args:
            api_base_url (str): The base url for the cloud hosted git API. If using LOCAL schema,
                                This should be the path to the directory containing locally checked
                                out git repos with structure: api_base_url/owner/repo.
            schema (GitSchema): The type of schema to use.
            access_token (str): The personal access token for the git API. Note this is not needed
                                for LOCAL schema.

        """
        self._logger = logging.getLogger(__name__).getChild(self.__class__.__name__)
        self._api_base_url = api_base_url
        self._schema = schema
        self._token = access_token

    def _call_api(self, url, params=None):
        """
        Call to the Git API.

        Args:
            url: Fully-qualified git provider API URL to request.
            params: Optional query parameters for the provider request.

        Returns:
            object: Decoded JSON response from the configured git provider.
        """
        headers = {}
        if self._token and self._schema == GitSchema.GITHUB:
            headers.update({"Authorization": "token %s" % self._token})
        elif self._token and self._schema == GitSchema.GITLAB:
            headers.update({"Private-Token": self._token})

        self._logger.debug("Using Git API (%s): %s", self._schema.name, url)
        self._logger.debug("->with params: %s", params)
        # self._logger.debug("->and headers: %s", headers)  # maybe dont disclose token in log.
        with http_error_handle(Exception, 500,
                               "Git API (%s) call failed" % self._schema.name):
            result = httpx.get(url, params=params, headers=headers)

        status_code = result.status_code
        if status_code != 200:
            raise HTTPException(500, "Git API (%s) returned code: %d"
                                % (self._schema.name, status_code))
        return result.json()

# TODO: Add the VerifiedUser and Admin user imports here
class GitTagListing(GitListingBase):
    """
    Github/lab Tag listing service.
    """
    def post(self, owner: str, repo: str, data: dict = Body(...),
             user=Depends(get_verified_user)):
        """
        HTTP POST request handler.

        Args:
            owner: Repository owner or namespace.
            repo: Repository name.
            data: JSON body containing sort options for tag names.
            user: Verified user dependency required to access the endpoint.

        Returns:
            list[str]: Tag names, optionally sorted.
        """
        self._logger.debug("IN POST: owner=%r, repo=%r, data=%r" %
                           (owner, repo, data))
        sort = data.get("sort", False)
        if not isinstance(sort, bool):
            raise HTTPException(400,
                                "Bad type: sort parameter to be of type bool, got (%r, %s)"
                                % (sort, type(sort)))
        sort_reversed = data.get("sort-reversed", False)
        if not isinstance(sort_reversed, bool):
            raise HTTPException(400,
                                "Bad type: sort-reversed parameter to be of type bool, "
                                "got (%r, %s)" % (sort, type(sort)))
        if sort and sort_reversed:
            raise HTTPException(400,
                                "Bad request, can't set both sort and sort-reversed "
                                "parameters to True.")

        sort_type = data.get("sort-type", None)
        if sort_type not in SORT_TYPE_MAPPING:
            raise HTTPException(400,
                                "Bad type: expected sort-type to be one of %s, "
                                "got %s" % (list(SORT_TYPE_MAPPING),
                                            sort_type))
        sort_type = SORT_TYPE_MAPPING[sort_type]

        # Get tags.
        # ################
        if self._schema == GitSchema.LOCAL:
            with http_error_handle(NoSuchPathError, 404,
                                   "No such local git repo %s/%s" % (owner, repo)),\
                 http_error_handle(InvalidGitRepositoryError, 500,
                                   "Invalid git repo %s/%s" % (owner, repo)):
                tags = (tag.name for tag in
                        Repo(os.path.join(self._api_base_url, owner, repo)).tags)

        elif self._schema == GitSchema.GITHUB:
            url = os.path.join(self._api_base_url,
                               owner,
                               repo,
                               "git",
                               "refs",
                               "tags")
            tags = (os.path.basename(x['ref']) for x in self._call_api(url))

        elif self._schema == GitSchema.GITLAB:
            url = os.path.join(self._api_base_url,
                               "projects",
                               "{owner}%2F{repo}".format(owner=owner, repo=repo),  # %2F = /
                               "repository",
                               "tags")
            tags = (x['name'] for x in self._call_api(url))
        else:
            msg = "Schema %r doesn't match any enum value." % self._schema
            self._logger.error(msg)
            raise HTTPException(500, msg)

        # Format output
        # #############
        output = list(tags)
        if sort or sort_reversed:
            output.sort(reverse=sort_reversed, key=sort_type)
        return output

    def router(self) -> APIRouter:
        """
        Build the router for this service.

        Returns:
            APIRouter: Router exposing the git tag listing endpoint.
        """
        router = APIRouter()
        router.add_api_route("/{owner}/{repo}", self.post, methods=["POST"])
        return router



class GitDirectoryListing(GitListingBase):
    """
    Github/lab Directory listing service.
    """
    def post(self, owner: str, repo: str, path: str = '/', data: dict = Body(...),
             user=Depends(get_verified_user)):
        """
        HTTP POST request handler.

        Args:
            owner: Repository owner or namespace.
            repo: Repository name.
            path: Repository directory path to list.
            data: JSON body containing regex, type, ref/tag, and optional sort controls.
            user: Verified user dependency required to access the endpoint.

        Returns:
            list[str]: Matching repository directory and/or file names.
        """
        self._logger.debug("IN POST: owner=%r, repo=%r, path=%r, data=%r" %
                           (owner, repo, path, data))

        # Data sanity checking
        # ####################
        with http_error_handle(Exception, 400, "Bad RegEx"):
            regex = re.compile(data.get('regex', r'.*'))

        list_type = data.get('type', 'all').lower()
        if list_type not in ("dirs", "files", "all"):
            raise HTTPException(400,
                                "Bad type: expected one of ('dirs', 'files', 'all'), got %s"
                                % list_type)

        sort = data.get("sort", False)
        if not isinstance(sort, bool):
            raise HTTPException(400,
                                "Bad type: sort parameter to be of type bool, got (%r, %s)"
                                % (sort, type(sort)))
        sort_reversed = data.get("sort-reversed", False)
        if not isinstance(sort_reversed, bool):
            raise HTTPException(400,
                                "Bad type: sort-reversed parameter to be of type bool, "
                                "got (%r, %s)" % (sort, type(sort)))
        if sort and sort_reversed:
            raise HTTPException(400,
                                "Bad request, can't set both sort and sort-reversed "
                                "parameters to True.")

        sort_type = data.get("sort-type", None)
        if sort_type not in SORT_TYPE_MAPPING:
            raise HTTPException(400,
                                "Bad type: expected sort-type to be one of %s, "
                                "got %s" % (list(SORT_TYPE_MAPPING),
                                            sort_type))
        sort_type = SORT_TYPE_MAPPING[sort_type]

        tag = data.get("tag", "master")
        if not isinstance(tag, str):
            raise HTTPException(400,
                                "Bad type: expected tag to be of type str, "
                                "got (%r, %s)" % (tag, type(tag)))

        # List git directory
        # ##################
        params = {"ref": tag}
        if self._schema == GitSchema.LOCAL:
            with http_error_handle(IndexError, 404, "No such refs/tag: %s"),\
                 http_error_handle(KeyError, 404, "No Such path: %r" % path.lstrip('/')),\
                 http_error_handle(NoSuchPathError, 404,
                                   "No such local git repo %s/%s" % (owner, repo)),\
                 http_error_handle(InvalidGitRepositoryError, 500,
                                   "Invalid git repo %s/%s" % (owner, repo)):
                path_tree = Repo(os.path.join(self._api_base_url, owner, repo))\
                    .refs[tag]\
                    .commit\
                    .tree / path.lstrip('/')
            if path_tree.type != 'tree':
                raise HTTPException(400, "Path %r is not a directory. (type = %s)"
                                    % (path.lstrip('/'), path_tree.type))
            dirs = (item.name for item in path_tree.traverse(depth=1) if item.type == 'tree')
            files = (item.name for item in path_tree.traverse(depth=1) if item.type == 'blob')

        elif self._schema == GitSchema.GITHUB:
            url = os.path.join(self._api_base_url,
                               owner,
                               repo,
                               "contents",
                               path.lstrip('/'))
            listing = self._call_api(url, params)
            dirs = (x['name'] for x in listing if x['type'] == "dir")
            files = (x['name'] for x in listing if x['type'] == "file")

        elif self._schema == GitSchema.GITLAB:
            params.update(path=path)
            url = os.path.join(self._api_base_url,
                               "projects",
                               "{owner}%2F{repo}".format(owner=owner, repo=repo),  # %2F = /
                               "repository",
                               "tree")
            listing = self._call_api(url, params)
            dirs = (x['name'] for x in listing if x['type'] == "tree")
            files = (x['name'] for x in listing if x['type'] == "blob")
        else:
            msg = "Schema %r doesn't match any enum value." % self._schema
            self._logger.error(msg)
            raise HTTPException(500, msg)

        # Format output
        # #############
        output = []
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

    def router(self) -> APIRouter:
        """
        Build the router for this service.

        Returns:
            APIRouter: Router exposing the git directory listing endpoints.
        """
        router = APIRouter()
        router.add_api_route("/{owner}/{repo}", self.post, methods=["POST"])
        router.add_api_route("/{owner}/{repo}/{path:path}", self.post, methods=["POST"])
        return router
