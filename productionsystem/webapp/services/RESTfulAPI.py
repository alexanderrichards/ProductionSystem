import logging
import os
from distutils.util import strtobool
import cherrypy
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from productionsystem.apache_utils import check_credentials, admin_only, dummy_credentials
from productionsystem.sql.models import Services, Users, Requests, ParametricJobs, DiracJobs


@cherrypy.expose
@cherrypy.popargs('service_id')
class ServicesAPI(object):
    mount_point = 'services'
    logger = logging.getLogger(__name__).getChild("ServicesAPI")

    @classmethod
    @cherrypy.tools.accept(media='application/json')
    @cherrypy.tools.json_out()
    @dummy_credentials
#    @check_credentials
#    @admin_only
    def GET(cls, service_id=None):  # pylint: disable=invalid-name
        """REST Get method."""
        cls.logger.debug("In blah/GET: service_id = %s", service_id)

        if service_id is not None:
            with cherrypy.HTTPError.handle(ValueError, 400,
                                           "Expected service id %r to be an integer" % service_id):
                service_id = int(service_id)

        with cherrypy.HTTPError.handle(NoResultFound, 404, "No Service with id %s" % service_id),\
                cherrypy.HTTPError.handle(MultipleResultsFound, 500,
                                          "Multiple services with id %s" % service_id):
            return Services.get_services(service_id=service_id)


@cherrypy.expose
@cherrypy.popargs('user_id')
class UsersAPI(object):
    mount_point = 'users'
    logger = logging.getLogger(__name__).getChild("UsersAPI")

    @classmethod
    @cherrypy.tools.accept(media='application/json')
    @cherrypy.tools.json_out()
    @dummy_credentials
#    @check_credentials
#    @admin_only
    def GET(cls, user_id=None):
        """REST GET method."""
        cls.logger.debug("In GET: user_id = %r", user_id)

        if user_id is not None:
            with cherrypy.HTTPError.handle(ValueError, 400,
                                           "Expected user id %r to be an integer" % user_id):
                user_id = int(user_id)

        with cherrypy.HTTPError.handle(NoResultFound, 404, "No user with id %s" % user_id),\
                cherrypy.HTTPError.handle(MultipleResultsFound, 500,
                                          "Multiple users with id %s" % user_id):
            return Users.get_users(user_id=user_id)

    @classmethod
#    @dummy_credentials
    @check_credentials
    @admin_only
    def PUT(cls, user_id, admin):  # pylint: disable=invalid-name
        """REST Put method."""
        cls.logger.warning("In PUT: user_id = %s, admin = %s", user_id, admin)

        with cherrypy.HTTPError.handle(ValueError, 400, 'Bad admin value'):
            admin = bool(strtobool(admin))

        # GET Code
        with cherrypy.HTTPError.handle(ValueError, 400,
                                       "Expected user id %r to be an integer" % user_id):
            user_id = int(user_id)

        with cherrypy.HTTPError.handle(NoResultFound, 404, "No user with id %s" % user_id),\
                cherrypy.HTTPError.handle(MultipleResultsFound, 500,
                                          "Multiple users with id %s" % user_id):
            user = Users.get_users(user_id=user_id)

        user.admin = admin
        user.update()


@cherrypy.expose
@cherrypy.popargs('diracjob_id')
class DiracJobsAPI(object):
    mount_point = 'diracjobs'
    logger = logging.getLogger(__name__).getChild("DiracJobsAPI")

    @classmethod
    @dummy_credentials
    def GET(cls, request_id, parametricjob_id, diracjob_id=None):
        print "request_id:", request_id, "parametricjob_id:", parametricjob_id, "diracjob_id:", diracjob_id
        return "WOOT"


@cherrypy.expose
@cherrypy.popargs('parametricjob_id')
class ParametricJobsAPI(object):
    mount_point = 'parametricjobs'
    logger = logging.getLogger(__name__).getChild("ParametricJobsAPI")
    diracjobs = DiracJobsAPI()

    @classmethod
    @cherrypy.tools.accept(media='application/json')
    @cherrypy.tools.json_out()
    #    @check_credentials
    @dummy_credentials
    def GET(cls, request_id, parametricjob_id=None):  # pylint: disable=invalid-name
        """
        REST Get method.

        Returns all ParametricJobs for a given request id.
        """
        cls.logger.debug("In GET: reqid = %s, parametricjob_id = %s", request_id, parametricjob_id)
        with cherrypy.HTTPError.handle(ValueError, 400, 'Bad request_id: %r' % request_id):
            request_id = int(request_id)


@cherrypy.expose
@cherrypy.popargs('request_id')
class RequestsAPI(object):
    mount_point = 'requests'
    logger = logging.getLogger(__name__).getChild("RequestsAPI")
    parametricjobs = ParametricJobsAPI()


    @classmethod
    @cherrypy.tools.accept(media='application/json')
    @cherrypy.tools.json_out()
    @dummy_credentials
#    @check_credentials
    def GET(cls, request_id=None):  # pylint: disable=invalid-name
        """REST Get method."""
        cls.logger.debug("In GET: reqid = %r", request_id)

        if request_id is not None:
            with cherrypy.HTTPError.handle(ValueError, 400, 'Bad request_id: %r' % request_id):
                request_id = int(request_id)

        requester = cherrypy.request.verified_user
        user_id = requester.id
        if requester.admin:
            user_id = None

        with cherrypy.HTTPError.handle(NoResultFound, 404, "No request with id %s" % request_id),\
                cherrypy.HTTPError.handle(MultipleResultsFound, 500,
                                          "Multiple requests with id %s" % request_id):
            response = Requests.get(request_id=request_id, user_id=user_id, load_user=True)

        if not isinstance(response, list):
            return dict(response.jsonable(), requester=response.requester.name)
        return [dict(request.jsonable(), requester=request.requester.name) for request in response]

    @classmethod
    @check_credentials
    @admin_only
    def DELETE(cls, request_id):  # pylint: disable=invalid-name
        """REST Delete method."""
        cls.logger.info("Deleting Request id: %s", request_id)

        with cherrypy.HTTPError.handle(ValueError, 400, 'Bad request_id: %r' % request_id):
            request_id = int(request_id)

        with cherrypy.HTTPError.handle(NoResultFound, 404, "No request with id %s" % request_id),\
                cherrypy.HTTPError.handle(MultipleResultsFound, 500,
                                          "Multiple requests with id %s" % request_id):
            Requests.delete(request_id)

def mount(root):
    for api in [ServicesAPI, UsersAPI, RequestsAPI]:
        cherrypy.tree.mount(api(), os.path.join(root, api.mount_point),
                            {'/': {'request.dispatch': cherrypy.dispatch.MethodDispatcher()}})





'''@cherrypy.expose
@cherrypy.popargs('request_id')
class Requests(objects):

    @classmethod
    @cherrypy.tools.accept(media='application/json')
    @cherrypy.tools.json_out()
    @dummy_credentials
#    @check_credentials
    def GET(cls, request_id=None):  # pylint: disable=invalid-name
        """REST Get method."""
        cls.logger.debug("In GET: reqid = %r", request_id)
        requester = cherrypy.request.verified_user

        if request_id is not None:
            with cherrypy.HTTPError.handle(ValueError, 400, 'Bad request_id: %r' % request_id):
                request_id = int(request_id)

        with managed_session() as session:
            if not requester.admin:
                query = session.query(cls).filter_by(requester_id=requester.id)
                if request_id is None:
                    cls._datatable_format_headers()
                    requests = query.all()
                    session.expunge_all()
                    return requests
                try:
                    request = query.filter_by(id=request_id).one()
                except NoResultFound:
                    message = "No Request found with id: %s" % request_id
                    cls.logger.warning(message)
                    raise cherrypy.NotFound(message)
                except MultipleResultsFound:
                    message = "Multiple Requests found with id: %s!" % request_id
                    cls.logger.error(message)
                    raise cherrypy.HTTPError(500, message)
                session.expunge(request)
                return request

            query = session.query(cls, Users)
            if request_id is None:
                cls._datatable_format_headers()
                return [dict(request.jsonable(),
                             requester=user.name)
                        for request, user in query.join(Users, cls.requester_id == Users.id).all()]
            try:
                request, user = query.filter_by(id=request_id)\
                                     .join(Users, cls.requester_id == Users.id)\
                                     .one()
            except NoResultFound:
                message = "No Request found with id: %s" % request_id
                cls.logger.warning(message)
                raise cherrypy.NotFound(message)
            except MultipleResultsFound:
                message = "Multiple Requests found with id: %s!" % request_id
                cls.logger.error(message)
                raise cherrypy.HTTPError(500, message)
            return dict(request.jsonable(),
                        requester=user.name)

    @classmethod
    @check_credentials
    @admin_only
    def DELETE(cls, request_id):  # pylint: disable=invalid-name
        """REST Delete method."""
        cls.logger.info("Deleting Request id: %s", request_id)
#        if not cherrypy.request.verified_user.admin:
#            raise cherrypy.HTTPError(401, "Unauthorised")
        with cherrypy.HTTPError.handle(ValueError, 400, 'Bad request_id: %r' % request_id):
            request_id = int(request_id)
        with managed_session() as session:
            try:
                #  request = session.query(Requests).filter_by(id=request_id).delete()
                request = session.query(cls).filter_by(id=request_id).one()
            except NoResultFound:
                message = "No Request found with id: %s" % request_id
                cls.logger.warning(message)
                raise cherrypy.NotFound(message)
            except MultipleResultsFound:
                message = "Multiple Requests found with id: %s!" % request_id
                cls.logger.error(message)
                raise cherrypy.HTTPError(500, message)

            session.delete(request)
            cls.logger.info("Request %d deleted.", request_id)

    @classmethod
#    @check_credentials
#    @admin_only
    @dummy_credentials
    def PUT(cls, request_id, status):  # pylint: disable=invalid-name
        """REST Put method."""
        cls.logger.debug("In PUT: reqid = %s, status = %s", request_id, status)
#        if not cherrypy.request.verified_user.admin:
#            raise cherrypy.HTTPError(401, "Unauthorised")
        with cherrypy.HTTPError.handle(ValueError, 400, 'Bad request_id: %r' % request_id):
            request_id = int(request_id)
        if status.upper() not in LocalStatus.members_names():
            raise cherrypy.HTTPError(400, "bad status")

        with managed_session() as session:
            try:
                request = session.query(cls).filter_by(id=request_id).one()
            except NoResultFound:
                message = "No Request found with id: %s" % request_id
                cls.logger.warning(message)
                raise cherrypy.NotFound(message)
            except MultipleResultsFound:
                message = "Multiple Requests found with id: %s!" % request_id
                cls.logger.error(message)
                raise cherrypy.HTTPError(500, message)

            request.status = LocalStatus[status.upper()]
            cls.logger.info("Request %d changed to status %s", request_id, status.upper())

    @classmethod
    @cherrypy.tools.json_in()
#    @check_credentials
    @dummy_credentials
    def POST(cls):  # pylint: disable=invalid-name
        """REST Post method."""
        data = cherrypy.request.json
        cls.logger.debug("In POST: kwargs = %s", data)
        if not isinstance(data, dict):
            message = "Request data is expected to be JSON object."
            cls.logger.error(message)
            raise cherrypy.HTTPError(400, message)
        if 'request' not in data:
            message = "Request data should contain 'request' as a subobject."
            cls.logger.error(message)
            raise cherrypy.HTTPError(400, message)
        data['request'].pop('requester_id', None)
        try:
            request = cls(requester_id=cherrypy.request.verified_user.id, **data["request"])
        except ValueError:
            message = "Error creating request, bad input."
            cls.logger.exception(message)
            raise cherrypy.HTTPError(400, message)

        parametricjobs = data.get("parametricjobs", [])
        if not parametricjobs:
            cls.logger.warning("No parametric jobs requested.")
        request.parametric_jobs = []
        for job in parametricjobs:
            try:
                job.pop('request_id', None)
                request.parametric_jobs.append(ParametricJobs(request_id=request.id, **job))
            except ValueError:
                message = "Error creating parametricjob, bad input."
                cls.logger.exception(message)
                raise cherrypy.HTTPError(400, message)
        with managed_session() as session:
            session.add(request)
            session.flush()
            session.refresh(request)
            cls.logger.info("New Request %d added", request.id)
'''