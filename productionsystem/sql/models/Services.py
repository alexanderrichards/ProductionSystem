"""Services Table."""
import json
import logging
from datetime import datetime
import cherrypy
from sqlalchemy import Column, Integer, String, TIMESTAMP, Enum
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from ..registry import managed_session
from ..enums import ServiceStatus
from ..SQLTableBase import SQLTableBase



@cherrypy.expose
@cherrypy.popargs('service_id')
class Services(SQLTableBase):
    """Services SQL Table."""

    __tablename__ = 'services'
    id = Column(Integer, primary_key=True)  # pylint: disable=invalid-name
    name = Column(String(30), nullable=False, unique=True)
    status = Column(Enum(ServiceStatus), nullable=False)
    timestamp = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    logger = logging.getLogger(__name__)

    def add(self):
        with managed_session() as session:
            session.add(self)
            session.flush()
            session.refresh(self)
            session.expunge(self)

    def update(self):
        with managed_session() as session:
            session.merge(self)

    @classmethod
    def get_services(cls, service_id=None, service_name=None):
        """
        Get service from database.

        Gets all services in database or explicitly those with a given service_name or service_id.

        Args:
            service_id (int): Service id to extract
            service_name (string): Service name to extract

        Returns:
            list/Services: The services/service pulled from the database
        """
        if service_name is not None:
            if not isinstance(service_name, basestring):
                cls.logger.error("Service name: %r should be of type str", service_name)
                raise TypeError

        if service_id is not None:
            try:
                service_id = int(service_id)
            except ValueError:
                cls.logger.error("Service id: %r should be of type int "
                                 "(or convertable to int)", service_id)
                raise

        with managed_session() as session:
            query = session.query(cls)
            query_id = []
            if service_id is not None:
                query = query.filter_by(id=service_id)
                query_id.append(str(service_id))
            if service_name is not None:
                query = query.filter_by(name=service_name)
                query_id.append(service_name)

            if service_id is None and service_name is None:
                services = query.all()
                session.expunge_all()
                return services

            try:
                service = query.one()
            except NoResultFound:
                cls.logger.warning("No result found for service: (%s)", ', '.join(query_id))
                raise
            except MultipleResultsFound:
                cls.logger.error("Multiple results found for service: (%s)", ', '.join(query_id))
                raise
            session.expunge(service)
            return service
'''
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
'''