"""HTML Page Server."""
from __future__ import annotations
import logging
from typing import Annotated
# from collections import defaultdict
from datetime import datetime, timezone
import jinja2
import hashlib
# import pkg_resources
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
# from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
# from productionsystem.config import getConfig
from productionsystem.sql.enums import ServiceStatus
from productionsystem.apache_utils import get_verified_user, admin_only
from productionsystem.webapp.jinja2_utils import jinja2_filter
# from productionsystem.sql import managed_session
from productionsystem.sql.models import Services, Service, Users, User, Requests, Request


VerifiedUser = Annotated[User, Depends(get_verified_user)]
AdminUser = Annotated[User, Depends(admin_only)]


@jinja2_filter
def gravitar_hash(email_add):
    """
    Hash an email address.

    Generate a gravitar compatible hash from an email address.
    Args:
        email_add (str): The target email address
    Returns:
        str: The hash string

    """
    return hashlib.md5(email_add.strip().lower().encode("utf-8")).hexdigest()


@jinja2_filter
def service_badge_url(service, service_name):
    """Return ShieldIO url for service badge."""
    name = service_name
    status = ServiceStatus.UNKNOWN
    if service is not None:
        name = service.name
        status = service.status
    return "https://img.shields.io/badge/{name}-{status.name}-{status.value}.svg"\
        .format(name=name, status=status)


@jinja2_filter
def log_splitter(log):
    """Split up the log string by line."""
    if log is None:
        return []
    return log.splitlines()


@jinja2_filter
def utc_datetime(value: datetime) -> str:
    """
    Convert a datetime to a UTC ISO 8601 string.

    Args:
        value (datetime): The datetime object to convert

    Returns:
        str: The UTC ISO 8601 formatted string

    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat(" ")


class HTMLPageServer(object):
    """The Web server."""

    def __init__(self, extra_jinja2_loader=None):
        """Initialise."""
        loader = jinja2.PackageLoader("productionsystem.webapp")
        if extra_jinja2_loader is not None:
            prefix_loader = jinja2.PrefixLoader({'productionsystem': loader})
            loader = jinja2.ChoiceLoader([prefix_loader,
                                          extra_jinja2_loader,
                                          loader])
        self._template_env = jinja2.Environment(loader=loader)
        self._logger = logging.getLogger(__name__)

    def _render(self, template_name, **kwargs):
        """Wrap the Jinja2 template getting and rendering boilerplate."""
        return self._template_env.get_template(template_name).render(**kwargs)

    def index(self, user: VerifiedUser):
        """Return the index page."""
        services = {service.name: Service.model_validate(service) for service in Services.get_services()}
        monitoring_service = services.get("monitoringd")
        if monitoring_service is None:
            services = {}
        elif monitoring_service.status != ServiceStatus.UP:
            services = {"monitoringd": monitoring_service}
        elif (datetime.now(timezone.utc) - monitoring_service.timestamp).total_seconds() > 1800.:  # 30 mins
            services = {}

        return HTMLResponse(self._render('dashboard_template.html',
                                         user=user,
                                         monitoringd_service=services.get("monitoringd"),
                                         dirac_service=services.get('DIRAC')))

    def admins(self, user: AdminUser):
        """Return admin management page."""
        users = [User.model_validate(user) for user in Users.get_users()]
        return HTMLResponse(self._render('admins_template.html', users=users))

    def newrequest(self, user: VerifiedUser):
        """Return new request page."""
        return HTMLResponse(self._render("newrequest_template.html"))

    def info(self, id: int, requester: VerifiedUser):
        """Return request info page."""
        selected_request = Request.model_validate(Requests.get(request_id=id,
                                                               user_id=None if requester.admin else requester.id,
                                                               load_user=True,
                                                               load_parametricjobs=True))
        return HTMLResponse(self._render('requestinfo_template.html', request=selected_request))

    def log(self, id: int, requester: VerifiedUser):
        """Return request log page."""
        selected_request = Request.model_validate(Requests.get(request_id=id,
                                                               user_id=None if requester.admin else requester.id,
                                                               load_user=True,
                                                               load_parametricjobs=True))
        # could remove the HTMLResponse as the response_class is already specified in the router
        return HTMLResponse(self._render('log_template.html', request=selected_request))

    def router(self) -> APIRouter:
        """Build the router for this service."""
        router = APIRouter()
        router.add_api_route("/", self.index, methods=["GET"], response_class=HTMLResponse)
        router.add_api_route("/admins", self.admins, methods=["GET"], response_class=HTMLResponse)
        router.add_api_route("/newrequest", self.newrequest, methods=["GET"], response_class=HTMLResponse)
        router.add_api_route("/info/{id}", self.info, methods=["GET"], response_class=HTMLResponse)
        router.add_api_route("/log/{id}", self.log, methods=["GET"], response_class=HTMLResponse)
        return router
