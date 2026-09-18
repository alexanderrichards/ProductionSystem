"""RESTful API."""
from __future__ import annotations

import logging
from distutils.util import strtobool  # pylint: disable=import-error, no-name-in-module
from fastapi import APIRouter, Body, Depends, Form, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from productionsystem.apache_utils import get_verified_user, admin_only
from productionsystem.sql.models import Services, Users, Requests, ParametricJobs, DiracJobs
from productionsystem.sql.models.Services import Service
from productionsystem.sql.models.Users import User
from productionsystem.sql.models.Requests import Request
from productionsystem.sql.models.ParametricJobs import ParametricJob
from productionsystem.sql.models.DiracJobs import DiracJob
from productionsystem.sql.enums import LocalStatus
from ._http import http_error_handle


class ServicesAPI(object):
    """Services RESTful API."""

    logger = logging.getLogger(__name__).getChild("ServicesAPI")

    def list(self, user: Users = Depends(admin_only)) -> list[Service]:
        """REST Get method: list all services."""
        self.logger.debug("In GET: service_id = None")
        return Services.get_services()

    def get(self, service_id: int, user: Users = Depends(admin_only)) -> Service:
        """REST Get method: get a single service."""
        self.logger.debug("In GET: service_id = %s", service_id)
        with http_error_handle(NoResultFound, 404, "No Service with id %s" % service_id), \
                http_error_handle(MultipleResultsFound, 500,
                                  "Multiple services with id %s" % service_id):
            return Services.get_services(service_id=service_id)

    def router(self) -> APIRouter:
        """Build the router for this service."""
        router = APIRouter()
        router.add_api_route("", self.list, methods=["GET"], response_model=list[Service])
        router.add_api_route("/{service_id}", self.get, methods=["GET"], response_model=Service)
        return router


class UsersAPI(object):
    """Users RESTful API."""

    logger = logging.getLogger(__name__).getChild("UsersAPI")

    def list(self, user: Users = Depends(admin_only)) -> list[User]:
        """REST GET method: list all users."""
        self.logger.debug("In GET: user_id = None")
        return Users.get_users()  # This is a list of SQLAlchemy ORM model instances but is converted to Pydantic models by FastAPI when the api route is added as router.add_api_route("", self.list, methods=["GET"], response_model=list[User])

    def get(self, user_id: int, user: Users = Depends(admin_only)) -> User:
        """REST GET method: get a single user."""
        self.logger.debug("In GET: user_id = %r", user_id)
        with http_error_handle(NoResultFound, 404, "No user with id %s" % user_id), \
                http_error_handle(MultipleResultsFound, 500,
                                  "Multiple users with id %s" % user_id):
            return Users.get_users(user_id=user_id)

    def put(self, user_id: int, admin: bool = Form(...), user: Users = Depends(admin_only)):
        """REST Put method."""
        self.logger.debug("In PUT: user_id = %s, admin = %s", user_id, admin)

        with http_error_handle(NoResultFound, 404, "No user with id %s" % user_id), \
                http_error_handle(MultipleResultsFound, 500,
                                  "Multiple users with id %s" % user_id):
            target_user = Users.get_users(user_id=user_id)

        target_user.admin = admin
        with http_error_handle(SQLAlchemyError, 500, "Error updating user %s(%d)"
                                                     % (target_user.name, user_id)):
            target_user.update()

    def router(self) -> APIRouter:
        """Build the router for this service."""
        router = APIRouter()
        router.add_api_route("", self.list, methods=["GET"], response_model=list[User])
        router.add_api_route("/{user_id}", self.get, methods=["GET"], response_model=User)
        router.add_api_route("/{user_id}", self.put, methods=["PUT"])
        return router


class DiracJobsAPI(object):
    """Dirac Jobs RESTful API."""

    logger = logging.getLogger(__name__).getChild("DiracJobsAPI")

    def list(self, request_id: int, parametricjob_id: int,
            user: Users = Depends(get_verified_user)) -> list[DiracJob]:
        """
        REST Get method.

        Returns all DiracJobs for a given request and parametricjob id.
        """
        self.logger.debug("In GET: reqid = %s, parametricjob_id = %s", request_id,
                          parametricjob_id)
        user_id = user.id
        if user.admin:
            user_id = None

        with http_error_handle(NoResultFound, 404,
                               "No dirac job with id %s" % parametricjob_id), \
                http_error_handle(MultipleResultsFound, 500,
                                  "Multiple dirac jobs with id %s" % parametricjob_id):
            return DiracJobs.get(parametricjob_id=parametricjob_id,
                                 request_id=request_id, user_id=user_id)

    def get(self, request_id: int, parametricjob_id: int, diracjob_id: int,
           user: Users = Depends(get_verified_user)) -> DiracJob:
        """REST Get method: get a single DiracJob."""
        self.logger.debug("In GET: reqid = %s, parametricjob_id = %s, diracjob_id = %s",
                          request_id, parametricjob_id, diracjob_id)
        user_id = user.id
        if user.admin:
            user_id = None

        with http_error_handle(NoResultFound, 404,
                               "No dirac job with id %s" % parametricjob_id), \
                http_error_handle(MultipleResultsFound, 500,
                                  "Multiple dirac jobs with id %s" % parametricjob_id):
            return DiracJobs.get(diracjob_id=diracjob_id, parametricjob_id=parametricjob_id,
                                 request_id=request_id, user_id=user_id)

    def router(self) -> APIRouter:
        """Build the router for this service."""
        router = APIRouter()
        router.add_api_route("", self.list, methods=["GET"], response_model=list[DiracJob])
        router.add_api_route("/{diracjob_id}", self.get, methods=["GET"], response_model=DiracJob)
        return router


class ParametricJobsAPI(object):
    """Parametric Jobs RESTful API."""

    logger = logging.getLogger(__name__).getChild("ParametricJobsAPI")

    def __init__(self):
        """Initialise."""
        self.diracjobs = DiracJobsAPI()

    def list(self, request_id: int,
            user: Users = Depends(get_verified_user)) -> list[ParametricJob]:
        """
        REST Get method.

        Returns all ParametricJobs for a given request id.
        """
        self.logger.debug("In GET: reqid = %s, parametricjob_id = None", request_id)
        user_id = user.id
        if user.admin:
            user_id = None

        with http_error_handle(NoResultFound, 404,
                               "No parametric job with id %d.None" % request_id), \
                http_error_handle(MultipleResultsFound, 500,
                                  "Multiple parametric jobs with id %d.None" % request_id):
            return ParametricJobs.get(request_id=request_id, user_id=user_id)

    def get(self, request_id: int, parametricjob_id: int,
           user: Users = Depends(get_verified_user)) -> ParametricJob:
        """REST Get method: get a single ParametricJob."""
        self.logger.debug("In GET: reqid = %s, parametricjob_id = %s", request_id,
                          parametricjob_id)
        user_id = user.id
        if user.admin:
            user_id = None

        with http_error_handle(NoResultFound, 404,
                               "No parametric job with id %d.%s"
                               % (request_id, parametricjob_id)), \
                http_error_handle(MultipleResultsFound, 500,
                                  "Multiple parametric jobs with id %d.%s"
                                  % (request_id, parametricjob_id)):
            return ParametricJobs.get(parametricjob_id=parametricjob_id,
                                     request_id=request_id, user_id=user_id)

    def put(self, request_id: int, parametricjob_id: int, reschedule: bool = Form(...),
           user: Users = Depends(get_verified_user)):
        """REST Put method."""
        self.logger.debug("In PUT: request_id = %s, jobid = %s, reschedule = %s",
                          request_id, parametricjob_id, reschedule)

        user_id = user.id
        if user.admin:
            user_id = None

        with http_error_handle(NoResultFound, 404,
                               "No parametric job with id %d.%d"
                               % (request_id, parametricjob_id)), \
                http_error_handle(MultipleResultsFound, 500,
                                  "Multiple parametric jobs with id %d.%d"
                                  % (request_id, parametricjob_id)):
            parametricjob = ParametricJobs.get(parametricjob_id=parametricjob_id,
                                               request_id=request_id, user_id=user_id)

        if reschedule\
                and parametricjob.status == LocalStatus.FAILED\
                and not parametricjob.reschedule:

            with http_error_handle(NoResultFound, 404,
                                   "No request with id %s" % request_id), \
                    http_error_handle(MultipleResultsFound, 500,
                                      "Multiple requests with id %s" % request_id):
                request = Requests.get(request_id=request_id, user_id=user_id)

            parametricjob.reschedule = True
            parametricjob.status = LocalStatus.SUBMITTING
            request.status = LocalStatus.SUBMITTING
            with http_error_handle(SQLAlchemyError, 500,
                                   "Error updating parametric job %d.%d"
                                   % (request_id, parametricjob_id)):
                parametricjob.update()
                request.update()

    def router(self) -> APIRouter:
        """Build the router for this service."""
        router = APIRouter()
        router.add_api_route("", self.list, methods=["GET"], response_model=list[ParametricJob])
        router.add_api_route("/{parametricjob_id}", self.get, methods=["GET"],
                             response_model=ParametricJob)
        router.add_api_route("/{parametricjob_id}", self.put, methods=["PUT"])
        router.include_router(self.diracjobs.router(),
                              prefix="/{parametricjob_id}/diracjobs")
        return router


class RequestsAPI(object):
    """Requests RESTful API."""

    logger = logging.getLogger(__name__).getChild("RequestsAPI")

    def __init__(self):
        """Initialise."""
        self.parametricjobs = ParametricJobsAPI()

    def list(self, user: Users = Depends(get_verified_user)) -> list[Request]:
        """REST Get method: list all requests."""
        self.logger.debug("In GET: reqid = None")
        user_id = user.id
        if user.admin:
            user_id = None

        with http_error_handle(NoResultFound, 404, "No request with id None"), \
                http_error_handle(MultipleResultsFound, 500, "Multiple requests with id None"):
            return Requests.get(user_id=user_id, load_user=True, load_parametricjobs=True)

    def get(self, request_id: int, user: Users = Depends(get_verified_user)) -> Request:
        """REST Get method: get a single request."""
        self.logger.debug("In GET: reqid = %r", request_id)
        user_id = user.id
        if user.admin:
            user_id = None

        with http_error_handle(NoResultFound, 404, "No request with id %s" % request_id), \
                http_error_handle(MultipleResultsFound, 500,
                                  "Multiple requests with id %s" % request_id):
            return Requests.get(request_id=request_id, user_id=user_id, load_user=True,
                                load_parametricjobs=True)

    def delete(self, request_id: int, user: Users = Depends(admin_only)):
        """REST Delete method."""
        self.logger.info("Deleting Request id: %s", request_id)

        with http_error_handle(NoResultFound, 404, "No request with id %s" % request_id), \
                http_error_handle(MultipleResultsFound, 500,
                                  "Multiple requests with id %s" % request_id):
            request = Requests.get(request_id=request_id)

        if request.status == LocalStatus.REMOVING:
            raise HTTPException(400, "Request %s is already marked for deletion" % request_id)

        request.status = LocalStatus.REMOVING
        with http_error_handle(SQLAlchemyError, 500,
                               "Error updating request with id %d" % request_id):
            request.update()
        self.logger.info("Request %d changed to status REMOVING", request_id)

    def post(self, data: dict = Body(...), user: Users = Depends(get_verified_user)):
        """REST Post method."""
        self.logger.debug("In POST: data = %s", data)
        if not isinstance(data, dict):
            raise HTTPException(400, "Request data is expected to be JSON object.")
        if 'request' not in data:
            raise HTTPException(400, "Request data should contain 'request' as a subobject.")

        data['request'].pop('requester_id', None)
        with http_error_handle(ValueError, 400, "Error creating request, bad input."):
            request = Requests(requester_id=user.id, **data["request"])

        with http_error_handle(SQLAlchemyError, 500, "Error adding request to DB."):
            request.add()
        self.logger.info("New request %d created", request.id)

    def put(self, request_id: int, status: str = Form(...), user: Users = Depends(admin_only)):
        """REST Put method."""
        self.logger.debug("In PUT: reqid = %s, status = %s", request_id, status)

        with http_error_handle(KeyError, 400, 'Bad status: %r' % status):
            status = LocalStatus[status.upper()]  # pylint: disable=unsubscriptable-object

        with http_error_handle(NoResultFound, 404, "No request with id %d" % request_id), \
                http_error_handle(MultipleResultsFound, 500,
                                  "Multiple requests with id %d" % request_id):
            request = Requests.get(request_id=request_id)

        if status == LocalStatus.APPROVED and request.status != LocalStatus.REQUESTED:
            raise HTTPException(410,
                                "Only requests in state Requested can transition to Approved.")
        if status == LocalStatus.CHECKED and request.status not in (LocalStatus.COMPLETED,
                                                                     LocalStatus.FAILED):
            raise HTTPException(411,
                                "Only requests in state Completed/Failed can transition to Checked.")
        if status == LocalStatus.CLOSED and request.status != LocalStatus.CHECKED:
            raise HTTPException(412,
                                "Only requests in state Checked can transition to Closed.")

        request.status = status
        with http_error_handle(SQLAlchemyError, 500,
                               "Error updating request with id %d" % request_id):
            request.update()
            self.logger.info("Request %d changed to status %s", request_id, status.name)

    def router(self) -> APIRouter:
        """Build the router for this service."""
        router = APIRouter()
        router.add_api_route("", self.list, methods=["GET"], response_model=list[Request])
        router.add_api_route("/{request_id}", self.get, methods=["GET"], response_model=Request)
        router.add_api_route("/{request_id}", self.delete, methods=["DELETE"])
        router.add_api_route("", self.post, methods=["POST"])
        router.add_api_route("/{request_id}", self.put, methods=["PUT"])
        router.include_router(self.parametricjobs.router(),
                              prefix="/{request_id}/parametricjobs")
        return router


def build_router() -> APIRouter:
    """Build the combined RESTful API router, mirroring the old CherryPy mount points."""
    router = APIRouter()
    router.include_router(ServicesAPI().router(), prefix="/services", tags=["services"])
    router.include_router(UsersAPI().router(), prefix="/users", tags=["users"])
    router.include_router(RequestsAPI().router(), prefix="/requests", tags=["requests"])
    return router
