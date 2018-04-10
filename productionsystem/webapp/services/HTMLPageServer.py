import logging
from datetime import datetime
import cStringIO
import jinja2
import pkg_resources
import cherrypy
from cherrypy.lib.static import serve_fileobj
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from productionsystem.apache_utils import check_credentials, dummy_credentials
from productionsystem.sql import managed_session
from productionsystem.sql.models import Services
from lzproduction.sql.statuses import SERVICESTATUS

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name
MINS = 60
#SERVICE_COLOUR_MAP = {SERVICESTATUS.Up: 'brightgreen',
#                      SERVICESTATUS.Down: 'red',
#                      SERVICESTATUS.Unknown: 'lightgrey',
#                      'stuck%3F': 'yellow'}  # %3F = ?


class HTMLPageServer(object):
    """The Web server."""

    def __init__(self):
        """Initialisation."""
        templates_dir = pkg_resources.resource_filename('productionsystem', 'webapp/resources')
        self.template_env = jinja2.Environment(loader=jinja2.FileSystemLoader(searchpath=templates_dir))

    @cherrypy.expose
    @dummy_credentials
    def index(self):
        """Return the index page."""
        data = {'title': 'ProductionSystem',
                'heading': 'Production System',
                'user': cherrypy.request.verified_user,
                'services': {}}
        with managed_session() as session:
            nonmonitoringd_services = session.query(Services)\
                                             .filter(Services.name != 'monitoringd')\
                                             .all()
            try:
                monitoringd = session.query(Services).filter_by(name='monitoringd').one()
            except NoResultFound:
                logger.warning("Monitoring daemon 'monitoringd' service status not in DB.")
                monitoringd = Services(name='monitoringd', status=SERVICESTATUS.Unknown, timestamp=datetime.utcnow())
            except MultipleResultsFound:
                logger.error("Multiple monitoring daemon 'monitoringd' services found in DB.")
                monitoringd = Services(name='monitoringd', status=SERVICESTATUS.Unknown, timestamp=datetime.utcnow())
            session.expunge_all()

        data['services'].update({monitoringd.name: monitoringd.status})
        out_of_date = (datetime.now() - monitoringd.timestamp).total_seconds() > 30. * MINS
        if monitoringd.status is not SERVICESTATUS.Up or out_of_date:
            nonmonitoringd_services = (Services(name=service.name, status=SERVICESTATUS.Unknown, timestamp=datetime.utcnow())
                                       for service in nonmonitoringd_services)
        data['services'].update({service.name: service.status for service in nonmonitoringd_services})
        return self.template_env.get_template('index.html').render(data)
