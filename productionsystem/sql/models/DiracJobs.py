"""Dirac Jobs Table."""
from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict, Field, field_serializer
from sqlalchemy import Column, TEXT, Integer, Enum, ForeignKey, ForeignKeyConstraint, select
from sqlalchemy.exc import NoResultFound, MultipleResultsFound

from productionsystem.sql.registry import managed_session
from ..enums import DiracStatus
from ..SQLTableBase import SQLTableBase


class DiracJob(BaseModel):
    """JSON-serialisable schema for a DiracJobs row."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(frozen=True)
    request_id: int = Field(frozen=True)
    parametricjob_id: int = Field(frozen=True)
    requester_id: int = Field(frozen=True)
    status: DiracStatus
    reschedules: int

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
    id = Column(Integer, primary_key=True)  # pylint: disable=invalid-name
    requester_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    request_id = Column(Integer, nullable=False)
    parametricjob_id = Column(Integer, nullable=False)
    status = Column(Enum(DiracStatus), nullable=False, default=DiracStatus.UNKNOWN)
    reschedules = Column(Integer, nullable=False, default=0)
    logger = logging.getLogger(__name__).getChild(__qualname__)

    @classmethod
    def get(cls, diracjob_id=None, request_id=None, parametricjob_id=None, user_id=None):
        """Get dirac jobs."""
        if diracjob_id is not None:
            try:
                diracjob_id = int(diracjob_id)
            except ValueError:
                cls.logger.error("Dirac job id: %r should be of type int "
                                 "(or convertable to int)", diracjob_id)
                raise

        if parametricjob_id is not None:
            try:
                parametricjob_id = int(parametricjob_id)
            except ValueError:
                cls.logger.error("Parametric job id: %r should be of type int "
                                 "(or convertable to int)", parametricjob_id)
                raise

        if request_id is not None:
            try:
                request_id = int(request_id)
            except ValueError:
                cls.logger.error("Request id: %r should be of type int "
                                 "(or convertable to int)", request_id)
                raise

        if user_id is not None:
            try:
                user_id = int(user_id)
            except ValueError:
                cls.logger.error("User id: %r should be of type int "
                                 "(or convertable to int)", user_id)
                raise

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
                                 parametricjob_id)
                raise
            return diracjob
