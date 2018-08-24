import logging
import os
from distutils.util import strtobool
import cherrypy
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from productionsystem.apache_utils import check_credentials, admin_only, dummy_credentials
from productionsystem.sql.models import Services, Users, Requests, ParametricJobs, DiracJobs
from productionsystem.sql.enums import LocalStatus


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
        cls.logger.debug("In GET: service_id = %s", service_id)

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
    @cherrypy.tools.accept(media='application/json')
    @cherrypy.tools.json_out()
#    @check_credentials
    @dummy_credentials
    def GET(cls, request_id, parametricjob_id, diracjob_id=None):  # pylint: disable=invalid-name
        """
        REST Get method.

        Returns all DiracJobs for a given request and parametricjob id.
        """
        cls.logger.debug("In GET: reqid = %s, parametricjob_id = %s, diracjob_id = %s",
                         request_id, parametricjob_id, diracjob_id)
        with cherrypy.HTTPError.handle(ValueError, 400, 'Bad request_id: %r' % request_id):
            request_id = int(request_id)
        with cherrypy.HTTPError.handle(ValueError, 400, 'Bad parametricjob_id: %r' % parametricjob_id):
            parametricjob_id = int(parametricjob_id)

        if diracjob_id is not None:
            with cherrypy.HTTPError.handle(ValueError, 400, 'Bad diracjob_id: %r' % diracjob_id):
                diracjob_id = int(diracjob_id)

        requester = cherrypy.request.verified_user
        user_id = requester.id
        if requester.admin:
            user_id = None

        with cherrypy.HTTPError.handle(NoResultFound, 404,
                                       "No dirac job with id %s" % parametricjob_id),\
                cherrypy.HTTPError.handle(MultipleResultsFound, 500,
                                          "Multiple dirac jobs with id %s" % parametricjob_id):
            return DiracJobs.get(diracjob_id=diracjob_id, parametricjob_id=parametricjob_id,
                                 request_id=request_id, user_id=user_id)


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

        if parametricjob_id is not None:
            with cherrypy.HTTPError.handle(ValueError, 400,
                                           'Bad parametricjob_id: %r' % parametricjob_id):
                parametricjob_id = int(parametricjob_id)

        requester = cherrypy.request.verified_user
        user_id = requester.id
        if requester.admin:
            user_id = None

        with cherrypy.HTTPError.handle(NoResultFound, 404,
                                       "No parametric job with id %s" % parametricjob_id),\
                cherrypy.HTTPError.handle(MultipleResultsFound, 500,
                                          "Multiple parametric jobs with id %s" % parametricjob_id):
            return ParametricJobs.get(parametricjob_id=parametricjob_id,
                                      request_id=request_id, user_id=user_id)

    @classmethod
    @check_credentials
    def PUT(cls, request_id, parametricjob_id, reschedule):  # pylint: disable=invalid-name
        """REST Put method."""
        cls.logger.debug("In PUT: request_id = %s, jobid = %s, reschedule = %s",
                         request_id, parametricjob_id, reschedule)

        with cherrypy.HTTPError.handle(ValueError, 400, 'Bad reschedule value'):
            reschedule = bool(strtobool(reschedule))

        # GET Code
        with cherrypy.HTTPError.handle(ValueError, 400, 'Bad request_id: %r' % request_id):
            request_id = int(request_id)

        with cherrypy.HTTPError.handle(ValueError, 400,
                                       'Bad parametricjob_id: %r' % parametricjob_id):
            parametricjob_id = int(parametricjob_id)

        requester = cherrypy.request.verified_user
        user_id = requester.id
        if requester.admin:
            user_id = None

        with cherrypy.HTTPError.handle(NoResultFound, 404,
                                       "No parametric job with id %s" % parametricjob_id),\
                cherrypy.HTTPError.handle(MultipleResultsFound, 500,
                                          "Multiple parametric jobs with id %s" % parametricjob_id):
            parametricjob = ParametricJobs.get(parametricjob_id=parametricjob_id,
                                               request_id=request_id, user_id=user_id)

        if parametricjob.status == LocalStatus.FAILED and not\
                parametricjob.reschedule and reschedule:
            parametricjob.reschedule = reschedule
            parametricjob.status = LocalStatus.SUBMITTING
            parametricjob.update()

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
            return Requests.get(request_id=request_id, user_id=user_id, load_user=True)

    @classmethod
    @check_credentials
    @admin_only
#    @dummy_credentials
    def DELETE(cls, request_id):  # pylint: disable=invalid-name
        """REST Delete method."""
        cls.logger.info("Deleting Request id: %s", request_id)

        with cherrypy.HTTPError.handle(ValueError, 400, 'Bad request_id: %r' % request_id):
            request_id = int(request_id)

        with cherrypy.HTTPError.handle(NoResultFound, 404, "No request with id %s" % request_id),\
                cherrypy.HTTPError.handle(MultipleResultsFound, 500,
                                          "Multiple requests with id %s" % request_id):
            Requests.delete(request_id)


    @classmethod
    @cherrypy.tools.json_in()
#    @check_credentials
    @dummy_credentials
    def POST(cls):  # pylint: disable=invalid-name
        """REST Post method."""
        data = cherrypy.request.json
        cls.logger.debug("In POST: kwargs = %s", data)
        if not isinstance(data, dict):
            raise cherrypy.HTTPError(400, "Request data is expected to be JSON object.")
        if 'request' not in data:
            raise cherrypy.HTTPError(400, "Request data should contain 'request' as a subobject.")

        data['request'].pop('requester_id', None)
        with cherrypy.HTTPError.handle(ValueError, 400, "Error creating request, bad input."):
            request = Requests(requester_id=cherrypy.request.verified_user.id, **data["request"])

        with cherrypy.HTTPError.handle(SQLAlchemyError, 500, "Error adding request to DB."):
            request.add()
        cls.logger.info("New request %d created", request.id)

def mount(root):
    for api in [ServicesAPI, UsersAPI, RequestsAPI]:
        cherrypy.tree.mount(api(), os.path.join(root, api.mount_point),
                            {'/': {'request.dispatch': cherrypy.dispatch.MethodDispatcher()}})
