"""CVMFS Directory Listing Service."""
import os
import re
import cherrypy
from productionsystem.apache_utils import dummy_credentials, check_credentials, admin_only


@cherrypy.expose
class CVMFSDirectoryListing(object):
    """CVMFS Directory listing service."""

    def _cp_dispatch(self, vpath):
        cherrypy.request.params['path'] = os.path.join(*vpath)
        while vpath:
            vpath.pop()
        return self

    @cherrypy.tools.accept(media='application/json')
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    @dummy_credentials
#    @check_credentials
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

        target = os.path.join('/cvmfs', path)
        try:
            _, dirs, files = os.walk(target).next()
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
        return output
