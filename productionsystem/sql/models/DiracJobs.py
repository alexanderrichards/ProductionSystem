"""Dirac Jobs Table."""
from __future__ import annotations

import logging
from typing import overload

from pydantic import BaseModel, ConfigDict, Field, field_serializer
from sqlalchemy import Column, TEXT, Integer, Enum, ForeignKey, ForeignKeyConstraint, select
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.exc import NoResultFound, MultipleResultsFound

from productionsystem.sql.registry import managed_session
from ..enums import DiracStatus
from ..SQLTableBase import SQLTableBase


class DiracJob(BaseModel):
    """JSON-serialisable schema for a DiracJobs row."""

    model_config = ConfigDict(from_attributes=True, validate_assignment=True)

    id: int = Field(frozen=True)
    request_id: int = Field(frozen=True)
    parametricjob_id: int = Field(frozen=True)
    requester_id: int = Field(frozen=True)
    status: DiracStatus = Field(frozen=True)
    reschedules: int = Field(frozen=True)

    @field_serializer("status")
    def _serialize_status(self, value: DiracStatus) -> str:
        return value.name.capitalize()


class DiracJobs(SQLTableBase):
    """Dirac Jobs SQL Table."""

    __tablename__ = 'diracjobs'
    classtype = Column(TEXT)
    __mapper_args__ = {'polymorphic_on': classtype,
                       'polymorphic_identity': 'diracjobs',
                       'with_polymorphic': '*'}
    __table_args__ = (ForeignKeyConstraint(['request_id', 'parametricjob_id'],
                                           ['parametricjobs.request_id', 'parametricjobs.id']),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # pylint: disable=invalid-name
    requester_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False)
    request_id: Mapped[int] = mapped_column(Integer, nullable=False)
    parametricjob_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[DiracStatus] = mapped_column(Enum(DiracStatus), nullable=False, default=DiracStatus.UNKNOWN)
    reschedules: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    logger = logging.getLogger(__name__).getChild(__qualname__)


    @overload
    @classmethod
    def get(cls) -> list[DiracJobs]: ...

    @overload
    @classmethod
    def get(cls, *, diracjob_id: int) -> DiracJobs: ...

    @overload
    @classmethod
    def get(cls, *, request_id: int) -> list[DiracJobs]: ...

    @overload
    @classmethod
    def get(cls, *, parametricjob_id: int) -> list[DiracJobs]: ...

    @overload
    @classmethod
    def get(cls, *, user_id: int) -> list[DiracJobs]: ...

    @overload
    @classmethod
    def get(cls, *, request_id: int, parametricjob_id: int) -> list[DiracJobs]: ...

    @overload
    @classmethod
    def get(cls, *, request_id: int, parametricjob_id: int, user_id: int) -> list[DiracJobs]: ...

    @overload
    @classmethod
    def get(cls, *, request_id: int, parametricjob_id: int, user_id: None) -> list[DiracJobs]: ...

    @overload
    @classmethod
    def get(cls, *, diracjob_id: int, request_id: int, parametricjob_id: int, user_id: int) -> DiracJobs: ...

    @overload
    @classmethod
    def get(cls, *, diracjob_id: int, request_id: int, parametricjob_id: int, user_id: None) -> DiracJobs: ...
    

    @classmethod
    def get(cls,
            *,
            diracjob_id: int | None = None,
            request_id: int | None = None,
            parametricjob_id: int | None = None,
            user_id: int | None = None) -> DiracJobs | list[DiracJobs]:
        """
        Get diracjobs from the database.

        Get all diracjobs in the database or explicitly those with a given diracjob_id, request_id, parametricjob_id
        or user_id.

        Args:
            diracjob_id (int | None): diracjob id to extract. Defaults to None.
            request_id (int | None): request id to extract. Defaults to None.
            parametricjob_id (int | None): parametric job id to extract. Defaults to None.
            user_id (int | None): user id to extract. Defaults to None.

        Raises:
            TypeError: If any of the provided IDs are not of type int or cannot be converted to int.
            NoResultFound: If no diracjob matches the given criteria when a single diracjob_id is provided.
            MultipleResultsFound: If multiple diracjobs match the given criteria when a single diracjob_id is provided.

        Returns:
            DiracJobs | list[DiracJobs]: diracjob(s) matching the given criteria.
        """
        if diracjob_id is not None:
            try:
                diracjob_id = int(diracjob_id)
            except ValueError as err:
                cls.logger.error("Dirac job id: %r should be of type int (or convertable to int)", diracjob_id)
                raise TypeError(f"Dirac job id: {diracjob_id!r} should be of type int (or convertable to int)") from err

        if parametricjob_id is not None:
            try:
                parametricjob_id = int(parametricjob_id)
            except ValueError as err:
                cls.logger.error("Parametric job id: %r should be of type int (or convertable to int)",
                                 parametricjob_id)
                raise TypeError(f"Parametric job id: {parametricjob_id!r} should be of type int "
                                "(or convertable to int)") from err

        if request_id is not None:
            try:
                request_id = int(request_id)
            except ValueError as err:
                cls.logger.error("Request id: %r should be of type int (or convertable to int)", request_id)
                raise TypeError(f"Request id: {request_id!r} should be of type int (or convertable to int)") from err

        if user_id is not None:
            try:
                user_id = int(user_id)
            except ValueError as err:
                cls.logger.error("User id: %r should be of type int (or convertable to int)", user_id)
                raise TypeError(f"User id: {user_id!r} should be of type int (or convertable to int)") from err

        with managed_session() as session:
            stmt = select(cls)
            if diracjob_id is not None:
                stmt = stmt.where(cls.id == diracjob_id)
            if parametricjob_id is not None:
                stmt = stmt.where(cls.parametricjob_id == parametricjob_id)
            if request_id is not None:
                stmt = stmt.where(cls.request_id == request_id)
            if user_id is not None:
                stmt = stmt.where(cls.requester_id == user_id)

            if diracjob_id is None:
                return session.scalars(stmt).all()

            try:
                diracjob = session.scalars(stmt).one()
            except NoResultFound:
                cls.logger.warning("No result found for dirac job id: %d", diracjob_id)
                raise
            except MultipleResultsFound:
                cls.logger.error("Multiple results found for dirac job id: %d",
                                 diracjob_id)
                raise
            return diracjob
