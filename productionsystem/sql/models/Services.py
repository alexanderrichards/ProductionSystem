"""Services Table."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from future.utils import native, native_str
from typing import overload
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from sqlalchemy import Column, Integer, String, TIMESTAMP, Enum, select
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.exc import NoResultFound, MultipleResultsFound
from ..registry import managed_session
from ..enums import ServiceStatus
from ..SQLTableBase import SQLTableBase


class Service(BaseModel):
    """JSON-serialisable schema for a Services row."""

    model_config = ConfigDict(from_attributes=True, validate_assignment=True)

    id: int = Field(frozen=True)
    name: str = Field(frozen=True)
    status: ServiceStatus = Field(frozen=True)
    timestamp: datetime = Field(frozen=True)

    @field_serializer("status")
    def _serialize_status(self, value: ServiceStatus) -> str:
        return value.name.capitalize()

    @field_serializer("timestamp")
    def _serialize_timestamp(self, value: datetime) -> str:
        return value.isoformat(' ')


class Services(SQLTableBase):
    """Services SQL Table."""

    __tablename__ = 'services'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # pylint: disable=invalid-name
    name: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    status: Mapped[ServiceStatus] = mapped_column(Enum(ServiceStatus), nullable=False, default=ServiceStatus.UNKNOWN)
    timestamp: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
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


    @overload
    @classmethod
    def get_services(cls) -> list[Services]: ...

    @overload
    @classmethod
    def get_services(cls, *, service_id: int) -> Services: ...

    @overload
    @classmethod
    def get_services(cls, *, service_name: str) -> Services: ...

    @classmethod
    def get_services(cls,
                     *,
                     service_id: int | None = None,
                     service_name: str | None = None) -> Services | list[Services]:
        """
        Get services from database.

        Gets all services in database or explicitly those with a given service_name or service_id.

        Args:
            service_id (int | None): Service id to extract. Defaults to None.
            service_name (string | None): Service name to extract. Defaults to None.

        Raises:
            TypeError: If service_id is not an int (or convertable to int) or service_name is not a str.
            NoResultFound: If no service matches the given criteria when a single service_id or service_name
                           is provided.
            MultipleResultsFound: If multiple services match the given criteria when a single service_id or
                                  service_name is provided.

        Returns:
            Services | list[Services]: The service/services pulled from the database

        """
        if service_name is not None and not isinstance(service_name, str):
            cls.logger.error("Service name: %r should be of type str", service_name)
            raise TypeError

        if service_id is not None:
            try:
                service_id = int(service_id)
            except ValueError as err:
                cls.logger.error("Service id: %r should be of type int (or convertable to int)", service_id)
                raise TypeError(f"Service id: {service_id!r} should be of type int (or convertable to int)") from err

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
