"""CVMFS Directory Listing Service."""
# Py2/3 compatibility layer
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *  # pylint: disable=wildcard-import, unused-wildcard-import, redefined-builtin

import os
import re
from distutils.version import StrictVersion  # pylint: disable=import-error, no-name-in-module
import cherrypy
from productionsystem.apache_utils import check_credentials


@cherrypy.expose
class CVMFSDirectoryListing(object):
    """CVMFS Directory listing service."""

    sort_type_map = {None: None,
                     'versions': StrictVersion}

    def _cp_dispatch(self, vpath):
        cherrypy.request.params['path'] = os.path.join(*vpath)
        while vpath:
            vpath.pop()
        return self

    @cherrypy.tools.accept(media='application/json')
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    @check_credentials
    def POST(self, path):  # pylint: disable=invalid-name
        """HTTP POST request handler."""
        data = cherrypy.request.json
        with cherrypy.HTTPError.handle(KeyError, 400, "No regex key"):
            regex = data['regex']
        with cherrypy.HTTPError.handle(Exception, 400, "Bad RegEx"):
            regex = re.compile(regex)
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
        if sort_type not in CVMFSDirectoryListing.sort_type_map:
            raise cherrypy.HTTPError(400,
                                     "Bad type: expected sort-type to be one of %s, "
                                     "got %s" % (list(CVMFSDirectoryListing.sort_type_map),
                                                 sort_type))
        sort_type = CVMFSDirectoryListing.sort_type_map[sort_type]

        target = os.path.join('/cvmfs', path)
        try:
            _, dirs, files = next(os.walk(target))
        except StopIteration:
            raise cherrypy.HTTPError(404, "Couldn't access '%s'" % target)

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
