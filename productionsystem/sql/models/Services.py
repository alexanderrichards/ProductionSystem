"""Services Table."""
import json
import logging
from datetime import datetime
import cherrypy
from sqlalchemy import Column, Integer, TEXT, TIMESTAMP, Enum
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from productionsystem.apache_utils import dummy_credentials
from ..registry import managed_session
from ..enums import ServiceStatus
from ..SQLTableBase import SQLTableBase
from ..JSONTableEncoder import JSONTableEncoder


def json_handler(*args, **kwargs):
    """Handle JSON encoding of response."""
    value = cherrypy.serving.request._json_inner_handler(*args, **kwargs)
    return json.dumps(value, cls=JSONTableEncoder)


@cherrypy.expose
@cherrypy.popargs('service_id')
class Services(SQLTableBase):
    """Services SQL Table."""

    __tablename__ = 'services'
    id = Column(Integer, primary_key=True)  # pylint: disable=invalid-name
    name = Column(TEXT, nullable=False)
    status = Column(Enum(ServiceStatus), nullable=False)
    timestamp = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    logger = logging.getLogger(__name__)

    @classmethod
    @cherrypy.tools.accept(media='application/json')
    @cherrypy.tools.json_out(handler=json_handler)
    @dummy_credentials
#    @check_credentials
#    @admin_only
    def GET(cls, service_id=None):  # pylint: disable=invalid-name
        """REST Get method."""
        cls.logger.debug("In GET: service_id = %r", service_id)
        requester = cherrypy.request.verified_user
        with managed_session() as session:
            query = session.query(cls)
            if service_id is None:
                return query.all()

            try:
                service_id = int(service_id)
            except ValueError:
                query = query.filter_by(name=service_id)
            else:
                query = query.filter_by(id=service_id)

            try:
                service = query.one()
            except NoResultFound:
                message = 'No matching service found.'
                cls.logger.warning(message)
                raise cherrypy.NotFound(message)
            except MultipleResultsFound:
                message = 'Multiple matching services found.'
                cls.logger.error(message)
                raise cherrypy.HTTPError(500, message)
            return service
