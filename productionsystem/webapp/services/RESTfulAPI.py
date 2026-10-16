"""
RESTful API.
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Form, HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import MultipleResultsFound, NoResultFound, SQLAlchemyError

from productionsystem.apache_utils import AdminUser, RequestedStatus, VerifiedUser
from productionsystem.sql.enums import LocalStatus
from productionsystem.sql.models import ParametricJob, ParametricJobs, Request, RequestCreate, Requests
from productionsystem.sql.models.DiracJobs import DiracJob, DiracJobs
from productionsystem.sql.models.Services import Service, Services
from productionsystem.sql.models.Users import User, Users
from ._http import http_error_handle


class ServicesAPI:
    """
    Services RESTful API.
    """
    logger = logging.getLogger(__name__).getChild("ServicesAPI")

    def list(self, user: AdminUser) -> list[Services]:
        """
        REST Get method: list all services.

        Args:
            user: Admin user dependency required to list services.

        Returns:
            list[Services]: All service rows.
        """
        self.logger.debug("In GET: service_id = None")
        return Services.get_services()

    def get(self, service_id: int, user: AdminUser) -> Services:
        """
        REST Get method: get a single service.

        Args:
            service_id: Service ID to retrieve.
            user: Admin user dependency required to read services.

        Returns:
            Services: Service row matching ``service_id``.
        """
        self.logger.debug("In GET: service_id = %s", service_id)
        # Don't need to handle TypeError here because service_id is already typed as int by FastAPI.
        with (http_error_handle(NoResultFound, 404, f"No Service with id {service_id}"),
              http_error_handle(MultipleResultsFound, 500, f"Multiple services with id {service_id}")):
            return Services.get_services(service_id=service_id)

    def router(self) -> APIRouter:
        """
        Build the router for this service.

        Returns:
            APIRouter: Router exposing service API endpoints.
        """
        router = APIRouter()
        router.add_api_route("", self.list, methods=["GET"], response_model=list[Service])
        router.add_api_route("/{service_id}", self.get, methods=["GET"], response_model=Service)
        return router


class UsersAPI:
    """
    Users RESTful API.
    """
    logger = logging.getLogger(__name__).getChild("UsersAPI")

    def list(self, user: AdminUser) -> list[Users]:
        """
        REST GET method: list all users.

        Args:
            user: Admin user dependency required to list users.

        Returns:
            list[Users]: All user rows.
        """
        self.logger.debug("In GET: user_id = None")
        # This is a list of SQLAlchemy ORM model instances but is converted to Pydantic models by FastAPI when the api
        # route is added as router.add_api_route("", self.list, methods=["GET"], response_model=list[User])
        return Users.get_users()

    def get(self, user_id: int, user: AdminUser) -> Users:
        """
        REST GET method: get a single user.

        Args:
            user_id: User ID to retrieve or update.
            user: Admin user dependency required to read users.

        Returns:
            Users: User row matching ``user_id``.
        """
        self.logger.debug("In GET: user_id = %r", user_id)
        with (http_error_handle(NoResultFound, 404, f"No user with id {user_id}"),
              http_error_handle(MultipleResultsFound, 500, f"Multiple users with id {user_id}")):
            return Users.get_users(user_id=user_id)

    def put(self, user: AdminUser, user_id: int, admin: bool = Form(...)):
        """
        REST Put method.

        Args:
            user: Admin user dependency required to change admin flags.
            user_id: User ID whose admin flag should change.
            admin: New admin flag submitted as form data.
        """
        self.logger.debug("In PUT: user_id = %s, admin = %s", user_id, admin)

        with (http_error_handle(NoResultFound, 404, f"No user with id {user_id}"),
              http_error_handle(MultipleResultsFound, 500, f"Multiple users with id {user_id}")):
            target_user = Users.get_users(user_id=user_id)

        target_user.admin = admin
        with http_error_handle(SQLAlchemyError, 500, f"Error updating user {target_user.name}({user_id})"):
            target_user.update()

    def router(self) -> APIRouter:
        """
        Build the router for this service.

        Returns:
            APIRouter: Router exposing user API endpoints.
        """
        router = APIRouter()
        router.add_api_route("", self.list, methods=["GET"], response_model=list[User])
        router.add_api_route("/{user_id}", self.get, methods=["GET"], response_model=User)
        router.add_api_route("/{user_id}", self.put, methods=["PUT"])
        return router


class DiracJobsAPI:
    """
    Dirac Jobs RESTful API.
    """
    logger = logging.getLogger(__name__).getChild("DiracJobsAPI")

    def list(self, request_id: int, parametricjob_id: int, user: VerifiedUser) -> list[DiracJobs]:
        """
        REST Get method.

        Returns all DiracJobs for a given request and parametricjob id.

        Args:
            request_id: Parent request ID containing the DIRAC jobs.
            parametricjob_id: Parent parametric job ID containing the DIRAC jobs.
            user: Verified user whose permissions constrain job visibility.

        Returns:
            list[DiracJobs]: DIRAC jobs visible to the user for the parametric job.
        """
        self.logger.debug("In GET: reqid = %s, parametricjob_id = %s", request_id, parametricjob_id)
        return DiracJobs.get(parametricjob_id=parametricjob_id,
                             request_id=request_id,
                             user_id=None if user.admin else user.id)

    def get(self, request_id: int, parametricjob_id: int, diracjob_id: int, user: VerifiedUser) -> DiracJobs:
        """
        REST Get method: get a single DiracJob.

        Args:
            request_id: Parent request ID containing the DIRAC job.
            parametricjob_id: Parent parametric job ID containing the DIRAC job.
            diracjob_id: DIRAC job ID to retrieve.
            user: Verified user whose permissions constrain job visibility.

        Returns:
            DiracJobs: DIRAC job visible to the user matching the composite ID.
        """
        self.logger.debug("In GET: reqid = %s, parametricjob_id = %s, diracjob_id = %s",
                          request_id, parametricjob_id, diracjob_id)
        with (http_error_handle(NoResultFound, 404,
                                f"No dirac job with id {request_id}.{parametricjob_id}.{diracjob_id}"),
              http_error_handle(MultipleResultsFound, 500,
                                f"Multiple dirac jobs with id {request_id}.{parametricjob_id}.{diracjob_id}")):
            return DiracJobs.get(diracjob_id=diracjob_id,
                                 parametricjob_id=parametricjob_id,
                                 request_id=request_id,
                                 user_id=None if user.admin else user.id)

    def router(self) -> APIRouter:
        """
        Build the router for this service.

        Returns:
            APIRouter: Router exposing DIRAC job API endpoints.
        """
        router = APIRouter()
        router.add_api_route("", self.list, methods=["GET"], response_model=list[DiracJob])
        router.add_api_route("/{diracjob_id}", self.get, methods=["GET"], response_model=DiracJob)
        return router


class ParametricJobsAPI:
    """
    Parametric Jobs RESTful API.
    """
    logger = logging.getLogger(__name__).getChild("ParametricJobsAPI")

    def __init__(self):
        """
        Initialise.
        """
        self.diracjobs = DiracJobsAPI()

    def list(self, request_id: int, user: VerifiedUser) -> list[ParametricJobs]:
        """
        REST Get method.

        Returns all ParametricJobs for a given request id.

        Args:
            request_id: Parent request ID containing the parametric jobs.
            user: Verified user whose permissions constrain parametric job visibility.

        Returns:
            list[ParametricJobs]: Parametric jobs visible to the user for the request.
        """
        self.logger.debug("In GET: reqid = %s", request_id)
        return ParametricJobs.get(request_id=request_id, user_id=None if user.admin else user.id)

    def get(self, request_id: int, parametricjob_id: int, user: VerifiedUser) -> ParametricJobs:
        """
        REST Get method: get a single ParametricJob.

        Args:
            request_id: Parent request ID containing the parametric job.
            parametricjob_id: Parametric job ID to retrieve.
            user: Verified user whose permissions constrain parametric job visibility.

        Returns:
            ParametricJobs: Parametric job visible to the user matching the composite ID.
        """
        self.logger.debug("In GET: reqid = %s, parametricjob_id = %s", request_id, parametricjob_id)
        with (http_error_handle(NoResultFound, 404, f"No parametric job with id {request_id}.{parametricjob_id}"),
              http_error_handle(MultipleResultsFound, 500,
                                f"Multiple parametric jobs with id {request_id}.{parametricjob_id}")):
            return ParametricJobs.get(parametricjob_id=parametricjob_id,
                                      request_id=request_id,
                                      user_id=None if user.admin else user.id)

    def put(self, request_id: int, parametricjob_id: int, user: VerifiedUser, reschedule: bool = Form(...)):
        """
        REST Put method.

        Args:
            request_id: Parent request ID containing the parametric job.
            parametricjob_id: Parametric job ID to update.
            user: Verified user whose permissions constrain parametric job updates.
            reschedule: Form flag requesting resubmission of failed/stalled DIRAC jobs.
        """
        self.logger.debug("In PUT: request_id = %s, jobid = %s, reschedule = %s",
                          request_id, parametricjob_id, reschedule)

        user_id = None if user.admin else user.id
        with (http_error_handle(NoResultFound, 404, f"No parametric job with id {request_id}.{parametricjob_id}"),
              http_error_handle(MultipleResultsFound, 500,
                                f"Multiple parametric jobs with id {request_id}.{parametricjob_id}")):
            parametricjob = ParametricJobs.get(parametricjob_id=parametricjob_id,
                                               request_id=request_id,
                                               user_id=user_id)

        if (reschedule
            and parametricjob.status == LocalStatus.FAILED
            and not parametricjob.reschedule):

            with (http_error_handle(NoResultFound, 404, f"No request with id {request_id}"),
                  http_error_handle(MultipleResultsFound, 500, f"Multiple requests with id {request_id}")):
                request = Requests.get(request_id=request_id, user_id=user_id)

            parametricjob.reschedule = True
            parametricjob.status = LocalStatus.SUBMITTING
            request.status = LocalStatus.SUBMITTING
            with http_error_handle(SQLAlchemyError, 500,
                                   f"Error updating parametric job {request_id}.{parametricjob_id}"):
                parametricjob.update()
                request.update()

    def router(self) -> APIRouter:
        """
        Build the router for this service.

        Returns:
            APIRouter: Router exposing parametric job API endpoints.
        """
        router = APIRouter()
        router.add_api_route("", self.list, methods=["GET"], response_model=list[ParametricJob])
        router.add_api_route("/{parametricjob_id}", self.get, methods=["GET"], response_model=ParametricJob)
        router.add_api_route("/{parametricjob_id}", self.put, methods=["PUT"])
        router.include_router(self.diracjobs.router(), prefix="/{parametricjob_id}/diracjobs")
        return router


class RequestsAPI:
    """
    Requests RESTful API.
    """
    logger = logging.getLogger(__name__).getChild("RequestsAPI")

    def __init__(self):
        """
        Initialise.
        """
        self.parametricjobs = ParametricJobsAPI()

    def list(self, user: VerifiedUser) -> list[Requests]:
        """
        REST Get method: list all requests.

        Args:
            user: Verified user whose permissions constrain request visibility.

        Returns:
            list[Requests]: Requests visible to the user with requester and parametric jobs loaded.
        """
        self.logger.debug("In GET: reqid = None")
        return Requests.get(user_id=None if user.admin else user.id, load_user=True, load_parametricjobs=True)

    def get(self, request_id: int, user: VerifiedUser) -> Requests:
        """
        REST Get method: get a single request.

        Args:
            request_id: Request ID to retrieve.
            user: Verified user whose permissions constrain request visibility.

        Returns:
            Requests: Request visible to the user with requester and parametric jobs loaded.
        """
        self.logger.debug("In GET: reqid = %r", request_id)
        with (http_error_handle(NoResultFound, 404, f"No request with id {request_id}"),
              http_error_handle(MultipleResultsFound, 500, f"Multiple requests with id {request_id}")):
            return Requests.get(request_id=request_id,
                                user_id=None if user.admin else user.id,
                                load_user=True,
                                load_parametricjobs=True)

    def delete(self, request_id: int, user: AdminUser):
        """
        REST Delete method.

        Args:
            request_id: Request ID to mark for removal by the monitoring daemon.
            user: Admin user dependency required to delete requests.
        """
        self.logger.info("Deleting Request id: %s", request_id)

        with (http_error_handle(NoResultFound, 404, f"No request with id {request_id}"),
              http_error_handle(MultipleResultsFound, 500, f"Multiple requests with id {request_id}")):
            request = Requests.get(request_id=request_id)

        if request.status == LocalStatus.REMOVING:
            raise HTTPException(400, f"Request {request_id} is already marked for deletion")

        request.status = LocalStatus.REMOVING
        with http_error_handle(SQLAlchemyError, 500, f"Error updating request with id {request_id}"):
            request.update()
        self.logger.info("Request %d changed to status REMOVING", request_id)

    def post(self, user: VerifiedUser, data: dict = Body(...)):
        """
        REST Post method.

        Args:
            user: Verified user creating the request.
            data: JSON body containing a ``request`` object.
        """
        self.logger.debug("In POST: data = %s", data)
        if not isinstance(data, dict):
            raise HTTPException(400, "Request data is expected to be JSON object.")
        if 'request' not in data:
            raise HTTPException(400, "Request data should contain 'request' as a subobject.")

        request_data = data["request"]
        if not request_data:
            raise HTTPException(400, "Request 'request' subobject cannot be empty.")
        if not isinstance(request_data, dict):
            raise HTTPException(400, "Request 'request' subobject must be a JSON object.")

        with http_error_handle(ValidationError, 400, "Error validating request data.", logger=self.logger):
            validated_request_data = RequestCreate.model_validate(request_data)

        with (http_error_handle(ValueError, 400, "Error creating request, bad input.", logger=self.logger),
              http_error_handle(SQLAlchemyError, 500, "Error adding request to DB.", logger=self.logger)):
            request = Requests.create(requester_id=user.id, validated_request_data=validated_request_data)

        self.logger.info("New request %d created", request.id)

    # Coercing status to a LocalStatus enum would be done by value
    # i.e. int value but form provides string. We therefore use a fastAPI dependency to handle the conversion.
    def put(self, user: AdminUser, request_id: int, status: RequestedStatus):
        """
        REST Put method.

        Args:
            user: Admin user dependency required to update request status.
            request_id: Request ID whose status should change.
            status: Parsed target local status from form data.
        """
        self.logger.debug("In PUT: reqid = %s, status = %s", request_id, status)

        with (http_error_handle(NoResultFound, 404, "No request with id %d" % request_id),
              http_error_handle(MultipleResultsFound, 500, "Multiple requests with id %d" % request_id)):
            request = Requests.get(request_id=request_id)

        if status == LocalStatus.APPROVED and request.status != LocalStatus.REQUESTED:
            raise HTTPException(409, "Only requests in state Requested can transition to Approved.")
        if status == LocalStatus.CHECKED and request.status not in (LocalStatus.COMPLETED, LocalStatus.FAILED):
            raise HTTPException(409, "Only requests in state Completed/Failed can transition to Checked.")
        if status == LocalStatus.CLOSED and request.status != LocalStatus.CHECKED:
            raise HTTPException(409, "Only requests in state Checked can transition to Closed.")

        request.status = status
        with http_error_handle(SQLAlchemyError, 500, "Error updating request with id %d" % request_id):
            request.update()
            self.logger.info("Request %d changed to status %s", request_id, status.name)

    def router(self) -> APIRouter:
        """
        Build the router for this service.

        Returns:
            APIRouter: Router exposing request API endpoints.
        """
        router = APIRouter()
        router.add_api_route("", self.list, methods=["GET"], response_model=list[Request])
        router.add_api_route("/{request_id}", self.get, methods=["GET"], response_model=Request)
        router.add_api_route("/{request_id}", self.delete, methods=["DELETE"])
        router.add_api_route("", self.post, methods=["POST"])
        router.add_api_route("/{request_id}", self.put, methods=["PUT"])
        router.include_router(self.parametricjobs.router(), prefix="/{request_id}/parametricjobs")
        return router


def build_router() -> APIRouter:
    """
    Build the combined RESTful API router, mirroring the old CherryPy mount points.

    Returns:
        APIRouter: Combined API router for services, users, and requests.
    """
    router = APIRouter()
    router.include_router(ServicesAPI().router(), prefix="/services", tags=["services"])
    router.include_router(UsersAPI().router(), prefix="/users", tags=["users"])
    router.include_router(RequestsAPI().router(), prefix="/requests", tags=["requests"])
    return router
