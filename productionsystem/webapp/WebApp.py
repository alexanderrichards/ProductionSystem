"""
LZ Production Web Server.
"""
from __future__ import annotations

import importlib.resources

import uvicorn
from daemonize import Daemonize
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from productionsystem.apache_utils import get_dummy_user, get_verified_user
from productionsystem.sql.registry import SessionRegistry
from .services import CVMFSDirectoryListing, GitDirectoryListing, GitSchema, GitTagListing, HTMLPageServer, RESTfulAPI


class WebApp(Daemonize):
    """
    LZ Production Web Server Daemon.
    """
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
        """
        Initialise.

        Args:
            dburl: SQLAlchemy database URL used by the web application.
            socket_host: Host interface passed to Uvicorn.
            socket_port: TCP port passed to Uvicorn.
            thread_pool: Maximum concurrent Uvicorn connections.
            git_schema: Git provider schema enum or enum name.
            git_token: Access token used by GitHub/GitLab listing services.
            git_api_base_url: Base URL or local root for git listing services.
            extra_jinja2_loader: Optional additional Jinja2 template loader.
            mock_mode: If True, use dummy credentials and seed mock data.
            **kwargs: Additional options forwarded to ``Daemonize``.
        """
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
        """
        Stop the daemon and ignore a successful ``SystemExit``.
        
        Returns:
            object | None: Result from ``Daemonize.exit`` unless it exits successfully.
        """
        try:
            return super().exit()
        except SystemExit as err:
            if err.code != 0:
                raise

    def _create_app(self, static_resources_path):
        """
        Build and return the FastAPI application, mounting all services.

        Args:
            static_resources_path: Filesystem path mounted as the static-resource fallback.

        Returns:
            FastAPI: Application with HTML, CVMFS, git, REST, and static routes mounted.
        """
        app = FastAPI()

        app.include_router(HTMLPageServer(extra_jinja2_loader=self._extra_jinja2_loader).router())
        app.include_router(CVMFSDirectoryListing().router(), prefix='/cvmfs')
        app.include_router(GitDirectoryListing(api_base_url=self._git_api_base_url,
                                               schema=self._git_schema,
                                               access_token=self._git_token).router(),
                           prefix='/git')
        app.include_router(GitTagListing(api_base_url=self._git_api_base_url,
                                         schema=self._git_schema,
                                         access_token=self._git_token).router(),
                           prefix='/gittags')
        app.include_router(RESTfulAPI.build_router(), prefix='/api')

        if self._mock_mode:
            app.dependency_overrides[get_verified_user] = get_dummy_user

        # Mounted last so it only acts as a fallback for paths not matched by any of the routers
        # registered above, mirroring CherryPy's global tools.staticdir behaviour.
        app.mount('/', StaticFiles(directory=str(static_resources_path)), name='static')
        return app

    def main(self):
        """
        Daemon main.
        """
        SessionRegistry.setup(self._dburl)  # pylint: disable=no-member

        # Setup testing entry for mock mode.
        ####################################
        if self._mock_mode:
            from copy import deepcopy

            from productionsystem.apache_utils import DUMMY_USER
            from productionsystem.sql.registry import managed_session
            with managed_session() as session:
                session.add(deepcopy(DUMMY_USER))

        with importlib.resources.path('productionsystem.webapp',
                                      'static_resources') as static_resources_path:
            app = self._create_app(static_resources_path)
            uvicorn.run(app, host=self._socket_host, port=self._socket_port,
                       limit_concurrency=self._thread_pool)
