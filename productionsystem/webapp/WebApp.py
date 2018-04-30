"""LZ Production Web Server."""
import pkg_resources
import cherrypy
from daemonize import Daemonize
from productionsystem.sql.JSONTableEncoder import json_cherrypy_handler
from productionsystem.sql.registry import SessionRegistry, managed_session
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

    def _global_config(self):
        static_resources = pkg_resources.resource_filename('productionsystem', 'webapp/resources/static')
        config = {
            'global': {
                'tools.gzip.on': True,
                'tools.json_out.handler': json_cherrypy_handler,
                'tools.staticdir.root': static_resources,
                'tools.staticdir.on': True,
                'tools.staticdir.dir': '',
                'server.socket_host': self._socket_host,
                'server.socket_port': self._socket_port,
                'server.thread_pool': self._thread_pool,
                'tools.expires.on': True,
                'tools.expires.secs': 3,  # expire in an hour, 3 secs for debug
#                'checker.check_static_paths': None
            }
        }
        return config

    def _mount_points(self):
        cherrypy.tree.mount(HTMLPageServer(),
                            '/',
                            {'/': {'request.dispatch': cherrypy.dispatch.Dispatcher()}})
        cherrypy.tree.mount(Requests.unsafe_construct(),
                            '/requests',
                            {'/': {'request.dispatch': cherrypy.dispatch.MethodDispatcher()}})

        cherrypy.tree.mount(Services(),
                            '/services',
                            {'/': {'request.dispatch': cherrypy.dispatch.MethodDispatcher()}})

        cherrypy.tree.mount(Users(),
                            '/users',
                            {'/': {'request.dispatch': cherrypy.dispatch.MethodDispatcher()}})
    def main(self):
        """Daemon main."""
        ## Temporary testing
        #########################
        import os
        if os.path.exists(self._dburl[10:]):
            os.remove(self._dburl[10:])
        from productionsystem.config import ConfigSystem
        print ConfigSystem.get_instance().config
        ##########################

        SessionRegistry.setup(self._dburl)
        #temporary testing entry
        #######################
        from productionsystem.sql.models import ParametricJobs
        with managed_session() as session:
            session.add(Users(id=17, dn='/blah/CN=mydn/blah', ca='ca', email='test@email.com', suspended=False, admin=True))
#            session.add(Requests(id=1, requester_id=17, description="alex test job"))
#            session.add(ParametricJobs(id=3, request_id=1, status='FAILED', num_jobs=5 ))
        #######################

        cherrypy.config.update(self._global_config())  # global vars need updating global config
        self._mount_points()
        cherrypy.engine.start()
        cherrypy.engine.block()
