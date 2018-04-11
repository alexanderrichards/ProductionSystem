"""LZ Production Web Server."""
import cherrypy
from daemonize import Daemonize
from productionsystem.sql.registry import SessionRegistry
from productionsystem.sql.models import Requests, Services, Users
from .services import HTMLPageServer


class WebApp(Daemonize):
    """LZ Production Web Server Daemon."""

    def __init__(self,
                 dburl="sqlite:///",
                 socket_host='0.0.0.0',
                 socket_port=8080,
                 thread_pool=8,
                 **kwargs):
        """Initialisation."""
        super(WebApp, self).__init__(action=self.main, **kwargs)
        self._dburl = dburl
        self._socket_host = socket_host
        self._socket_port = socket_port
        self._thread_pool = thread_pool

    def main(self):
        """Daemon main."""
        SessionRegistry.setup(self._dburl)

        config = {
            'global': {
                'tools.gzip.on': True,
#                'tools.staticdir.root': html_resources,
#                'tools.staticdir.on': True,
#                'tools.staticdir.dir': '',
                'server.socket_host': self._socket_host,
                'server.socket_port': self._socket_port,
                'server.thread_pool': self._thread_pool,
                'tools.expires.on': True,
                'tools.expires.secs': 3,  # expire in an hour, 3 secs for debug
#                'checker.check_static_paths': None
            }
        }

        cherrypy.config.update(config)  # global vars need updating global config
        cherrypy.tree.mount(HTMLPageServer(),
                            '/',
                            {'/': {'request.dispatch': cherrypy.dispatch.Dispatcher()}})
        cherrypy.tree.mount(Requests(),
                            '/requests',
                            {'/': {'request.dispatch': cherrypy.dispatch.MethodDispatcher()}})

        cherrypy.tree.mount(Services(),
                            '/services',
                            {'/': {'request.dispatch': cherrypy.dispatch.MethodDispatcher()}})

        cherrypy.tree.mount(Users(),
                            '/users',
                            {'/': {'request.dispatch': cherrypy.dispatch.MethodDispatcher()}})
#        cherrypy.tree.mount(Admins(template_env),
#                            '/admins',
#                            {'/': {'request.dispatch': CredentialDispatcher(cherrypy.dispatch.MethodDispatcher(),
#                                                                                          admin_only=True)}})
        cherrypy.engine.start()
        cherrypy.engine.block()
