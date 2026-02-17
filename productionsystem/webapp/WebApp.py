"""LZ Production Web Server."""
from __future__ import annotations

import importlib

import cherrypy
from daemonize import Daemonize

from productionsystem.sql.JSONTableEncoder import json_cherrypy_handler
from productionsystem.sql.registry import SessionRegistry

from .services import (CVMFSDirectoryListing, GitDirectoryListing, GitSchema,
                       GitTagListing, HTMLPageServer, RESTfulAPI)


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
        """Initialise."""
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
        if not isinstance(git_schema, GitSchema):
            self._git_schema = GitSchema[git_schema]

    def exit(self):
        try:
            return super().exit()
        except SystemExit as err:
            if err.code != 0:
                raise

    def _global_config(self):
        with importlib.resources.path('productionsystem.webapp', 'static_resources') as static_resources_path:
            config = {
                'global': {
                    'log.screen': False,
                    'log.access_file': '',
                    'log.error_file': '',
                    'tools.gzip.on': True,
                    'tools.json_out.handler': json_cherrypy_handler,
                    'tools.staticdir.root': str(static_resources_path),
                    'tools.staticdir.on': True,
                    'tools.staticdir.dir': '',
                    'server.socket_host': self._socket_host,
                    'server.socket_port': self._socket_port,
                    'server.thread_pool': self._thread_pool,
                    'tools.expires.on': True,
                    'tools.expires.secs': 3,  # expire in an hour, 3 secs for debug
                    'tools.encode.text_only': False,
                    # py2/3 compatibility layer issue, py2 breaks with unicode path dummy.html
                    'checker.check_static_paths': None
                }
            }
        # Prevent CherryPy from trying to open its log files when the autoreloader kicks in.
        # This is not strictly required since we do not even let CherryPy open them in the
        # first place. But, this avoids wasting time on something useless.
        cherrypy.engine.unsubscribe('graceful', cherrypy.log.reopen_files)
        return config

    def _mount_points(self):
        cherrypy.tree.mount(HTMLPageServer(extra_jinja2_loader=self._extra_jinja2_loader),
                            '/',
                            {'/': {'request.dispatch': cherrypy.dispatch.Dispatcher()}})

        cherrypy.tree.mount(CVMFSDirectoryListing(),
                            '/cvmfs',
                            {'/': {'request.dispatch': cherrypy.dispatch.MethodDispatcher()}})
        cherrypy.tree.mount(GitDirectoryListing(api_base_url=self._git_api_base_url,
                                                schema=self._git_schema,
                                                access_token=self._git_token),
                            '/git',
                            {'/': {'request.dispatch': cherrypy.dispatch.MethodDispatcher()}})
        cherrypy.tree.mount(GitTagListing(api_base_url=self._git_api_base_url,
                                          schema=self._git_schema,
                                          access_token=self._git_token),
                            '/gittags',
                            {'/': {'request.dispatch': cherrypy.dispatch.MethodDispatcher()}})
        RESTfulAPI.mount('/api')

    def main(self):
        """Daemon main."""
        SessionRegistry.setup(self._dburl)  # pylint: disable=no-member

        # Setup testing entry for mock mode.
        ####################################
        if self._mock_mode:
            from copy import deepcopy

            from productionsystem.apache_utils import DUMMY_USER
            from productionsystem.sql.registry import managed_session
            with managed_session() as session:
                session.add(deepcopy(DUMMY_USER))

        cherrypy.config.update(self._global_config())  # global vars need updating global config
        self._mount_points()
        cherrypy.engine.start()
        cherrypy.engine.block()
