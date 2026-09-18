"""Services Table."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from future.utils import native, native_str
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from sqlalchemy import Column, Integer, String, TIMESTAMP, Enum, select
from sqlalchemy.exc import NoResultFound, MultipleResultsFound
from ..registry import managed_session
from ..enums import ServiceStatus
from ..SQLTableBase import SQLTableBase


class Service(BaseModel):
    """JSON-serialisable schema for a Services row."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(frozen=True)
    name: str = Field(frozen=True)
    status: ServiceStatus
    timestamp: datetime

    @field_serializer("status")
    def _serialize_status(self, value: ServiceStatus) -> str:
        return value.name.capitalize()

    @field_serializer("timestamp")
    def _serialize_timestamp(self, value: datetime) -> str:
        return value.isoformat(' ')


class Services(SQLTableBase):
    """Services SQL Table."""

    __tablename__ = 'services'
    id = Column(Integer, primary_key=True)  # pylint: disable=invalid-name
    name = Column(String(30), nullable=False, unique=True)
    status = Column(Enum(ServiceStatus), nullable=False, default=ServiceStatus.UNKNOWN)
    timestamp = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    logger = logging.getLogger(__name__).getChild(__qualname__)

    def add(self):
        """Add self to the DB."""
        with managed_session() as session:
            session.add(self)
            session.flush()
            session.refresh(self)

    def update(self):
        """Update the DB with current values."""
        with managed_session() as session:
            # Onupdate doesn't trigger if setting status field to same as current value as it's
            # no-op in some DBs.
            self.timestamp = datetime.now(timezone.utc)
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
            if not isinstance(service_name, (str, native_str)):
                cls.logger.error("Service name: %r should be of type str", service_name)
                raise TypeError

        if service_id is not None:
            try:
                service_id = native(int(service_id))
            except ValueError:
                cls.logger.error("Service id: %r should be of type int "
                                 "(or convertable to int)", service_id)
                raise

        with managed_session() as session:
            query_id = []
            stmt = select(cls)
            if service_id is not None:
                stmt = stmt.where(cls.id == service_id)
                query_id.append(str(service_id))
            if service_name is not None:
                stmt = stmt.where(cls.name == service_name)
                query_id.append(service_name)

            if service_id is None and service_name is None:
                services = session.scalars(stmt).all()
                return services

            try:
                service = session.scalars(stmt).one()
            except NoResultFound:
                cls.logger.warning("No result found for service: (%s)", ', '.join(query_id))
                raise
            except MultipleResultsFound:
                cls.logger.error("Multiple results found for service: (%s)", ', '.join(query_id))
                raise
            return service
