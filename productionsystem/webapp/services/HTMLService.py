"""HTML Page Server."""
# Py2/3 compatibility layer
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *  # pylint: disable=wildcard-import, unused-wildcard-import, redefined-builtin
from future.utils import native_str

import logging
# from collections import defaultdict
from datetime import datetime
import jinja2
import hashlib
# import pkg_resources
import cherrypy
# from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
# from productionsystem.config import getConfig
from productionsystem.sql.enums import ServiceStatus
from productionsystem.apache_utils import check_credentials, admin_only
from productionsystem.webapp.jinja2_utils import jinja2_filter
# from productionsystem.sql import managed_session
from productionsystem.sql.models import Services, Users, Requests


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

    @cherrypy.expose
    @check_credentials
    def index(self):
        """Return the index page."""
        services = {service.name: service for service in Services.get_services()}
        monitoring_service = services.get("monitoringd")
        if monitoring_service is None:
            services = {}
        elif monitoring_service.status != ServiceStatus.UP:
            services = {"monitoringd": monitoring_service}
        elif (datetime.utcnow() - monitoring_service.timestamp).total_seconds() > 1800.:  # 30 mins
            services = {}

        return self._render('dashboard_template.html',
                            user=cherrypy.request.verified_user,
                            monitoringd_service=services.get("monitoringd"),
                            dirac_service=services.get('DIRAC'))

    @cherrypy.expose
    @check_credentials
    @admin_only
    def admins(self):
        """Return admin management page."""
        users = Users.get_users()
        return self._render('admins_template.html', users=users)

    @cherrypy.expose
    @check_credentials
    def newrequest(self):
        """Return new request page."""
        return self._render("newrequest_template.html")

    @cherrypy.expose
    @check_credentials
    def info(self, id):
        """Return request info page."""
        requester = cherrypy.request.verified_user
        user_id = requester.id
        if requester.admin:
            user_id = None
        return self._render('requestinfo_template.html',
                            request=Requests.get(id, user_id=user_id,
                                                 load_user=True, load_parametricjobs=True))

    @cherrypy.expose
    @check_credentials
    def log(self, id):
        """Return request log page."""
        requester = cherrypy.request.verified_user
        user_id = requester.id
        if requester.admin:
            user_id = None
        return self._render('log_template.html',
                            request=Requests.get(id, user_id=user_id,
                                                 load_user=True, load_parametricjobs=True))
