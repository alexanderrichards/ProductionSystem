"""LZ Production Web Server."""
# Py2/3 compatibility layer
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *  # pylint: disable=wildcard-import, unused-wildcard-import, redefined-builtin
from future.utils import native_str

import pkg_resources
import cherrypy
from daemonize import Daemonize
from productionsystem.sql.JSONTableEncoder import json_cherrypy_handler
from productionsystem.sql.registry import SessionRegistry
from .services import (HTMLPageServer, CVMFSDirectoryListing, GitDirectoryListing,
                       GitTagListing, GitSchema, RESTfulAPI)


class WebApp(Daemonize):
    """LZ Production Web Server Daemon."""

    def __init__(self,
                 dburl="sqlite:///",
                 socket_host='0.0.0.0',
                 socket_port=8080,
                 thread_pool=8,
                 git_schema=GitSchema.GITHUB,
                 git_token='',
                 git_api_base_url="https://api.github.com/repos",
                 extra_jinja2_loader=None,
                 mock_mode=False,
                 **kwargs):
        """Initialisation."""
        super(WebApp, self).__init__(action=self.main, **kwargs)
        self._dburl = dburl
        self._socket_host = socket_host
        self._socket_port = socket_port
        self._thread_pool = thread_pool
        self._extra_jinja2_loader = extra_jinja2_loader
        self._mock_mode = mock_mode
        self._git_token = git_token
        self._git_api_base_url = git_api_base_url
        self._git_schema = git_schema
        if isinstance(git_schema, str):
            self._git_schema = GitSchema[git_schema]

    def _global_config(self):
        static_resources = pkg_resources.resource_filename('productionsystem',
                                                           'webapp/static_resources')
        config = {
            native_str('global'): {
                native_str('log.screen'): False,
                native_str('log.access_file'): native_str(''),
                native_str('log.error_file'): native_str(''),
                native_str('tools.gzip.on'): True,
                native_str('tools.json_out.handler'): json_cherrypy_handler,
                native_str('tools.staticdir.root'): native_str(static_resources),
                native_str('tools.staticdir.on'): True,
                native_str('tools.staticdir.dir'): '',
                native_str('server.socket_host'): native_str(self._socket_host),
                native_str('server.socket_port'): self._socket_port,
                native_str('server.thread_pool'): self._thread_pool,
                native_str('tools.expires.on'): True,
                native_str('tools.expires.secs'): 3,  # expire in an hour, 3 secs for debug
                native_str('tools.encode.text_only'): False,
                # py2/3 compatibility layer issue, py2 breaks with unicode path dummy.html
                native_str('checker.check_static_paths'): None
            }
        }
        # Prevent CherryPy from trying to open its log files when the autoreloader kicks in.
        # This is not strictly required since we do not even let CherryPy open them in the
        # first place. But, this avoids wasting time on something useless.
        cherrypy.engine.unsubscribe(native_str('graceful'), cherrypy.log.reopen_files)
        return config

    def _mount_points(self):
        cherrypy.tree.mount(HTMLPageServer(extra_jinja2_loader=self._extra_jinja2_loader),
                            native_str('/'),
                            {native_str('/'): {native_str('request.dispatch'):
                                               cherrypy.dispatch.Dispatcher()}})

        cherrypy.tree.mount(CVMFSDirectoryListing(),
                            native_str('/cvmfs'),
                            {native_str('/'): {native_str('request.dispatch'):
                                               cherrypy.dispatch.MethodDispatcher()}})
        cherrypy.tree.mount(GitDirectoryListing(api_base_url=self._git_api_base_url,
                                                schema=self._git_schema,
                                                access_token=self._git_token),
                            native_str('/git'),
                            {native_str('/'): {native_str('request.dispatch'):
                                               cherrypy.dispatch.MethodDispatcher()}})
        cherrypy.tree.mount(GitTagListing(api_base_url=self._git_api_base_url,
                                          schema=self._git_schema,
                                          access_token=self._git_token),
                            native_str('/gittags'),
                            {native_str('/'): {native_str('request.dispatch'):
                                               cherrypy.dispatch.MethodDispatcher()}})
        RESTfulAPI.mount(native_str('/api'))

    def main(self):
        """Daemon main."""
        SessionRegistry.setup(self._dburl)  # pylint: disable=no-member

        # Setup testing entry for mock mode.
        ####################################
        if self._mock_mode:
            from productionsystem.sql.registry import managed_session
            from productionsystem.apache_utils import DUMMY_USER
            from copy import deepcopy
            with managed_session() as session:
                session.add(deepcopy(DUMMY_USER))

        cherrypy.config.update(self._global_config())  # global vars need updating global config
        self._mount_points()
        cherrypy.engine.start()
        cherrypy.engine.block()
