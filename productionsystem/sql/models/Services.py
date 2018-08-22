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
    def get_services(cls, service_name=None, service_id=None):
        """
        Get service from database.

        Gets all services in database or explicitly those with a given service_name or service_id.

        Args:
            service_name (string): Service name to extract
            service_id (int): Service id to extract

        Returns:
            list/Services: The services/service pulled from the database
        """
        with managed_session() as session:
            query = session.query(cls)
            if service_id is None:
                if service_name is not None:
                    query = query.filter_by(name=service_name)
                services = query.all()
                if service_name is not None and not services:
                    cls.logger.warning("No results found for service name: %s", service_name)
                    raise NoResultFound
                session.expunge_all()
                return services

            try:
                service = query.filter_by(id=service_id).one()
            except NoResultFound:
                cls.logger.warning("No result found for service id: %d", service_id)
                raise
            except MultipleResultsFound:
                cls.logger.error("Multiple results found for service id: %d", service_id)
                raise
            session.expunge(service)
            return service

    @classmethod
    @cherrypy.tools.accept(media='application/json')
    @cherrypy.tools.json_out()
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
                services = query.all()
                session.expunge_all()
                return services

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
            session.expunge(service)
            return service
