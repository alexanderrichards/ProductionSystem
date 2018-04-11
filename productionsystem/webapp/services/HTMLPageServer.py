import logging
from collections import defaultdict
from datetime import datetime
import jinja2
import pkg_resources
import cherrypy
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from productionsystem.apache_utils import dummy_credentials
from productionsystem.sql import managed_session
from productionsystem.sql.models import Services
from productionsystem.enums import ServiceStatus

MINS = 60


class HTMLPageServer(object):
    """The Web server."""

    def __init__(self):
        """Initialisation."""
        templates_dir = pkg_resources.resource_filename('productionsystem', 'webapp/resources')
        self._template_env = jinja2.Environment(loader=jinja2.FileSystemLoader(searchpath=templates_dir))
        self._logger = logging.getLogger(__name__)

    @cherrypy.expose
    @dummy_credentials
    def index(self):
        """Return the index page."""
        data = {'title': 'ProductionSystem',
                'heading': 'Production System',
                'user': cherrypy.request.verified_user,
                'statuses': defaultdict(lambda: ServiceStatus.UNKNOWN)}
        with managed_session() as session:
            query = session.query(Services)
            try:
                monitoring_service = query.filter_by(name='monitoringd').one()
            except NoResultFound:
                self._logger.warning("Monitoring daemon 'monitoringd' service status not in DB.")
            except MultipleResultsFound:
                self._logger.warning("Multiple monitoring daemon 'monitoringd' services found in DB.")
            else:
                out_of_date = (datetime.utcnow() - monitoring_service.timestamp).total_seconds() > 30. * MINS
                monitoring_status = monitoring_service.status
                data['statuses']['monitoringd'] = monitoring_status
                if not out_of_date and monitoring_status == ServiceStatus.UP:
                    for service in query.filter(Services.name != 'monitoringd').all():
                        data['statuses'][service.name] = service.status
            return self._template_env.get_template('index.html').render(data)

