"""Requests Table."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from operator import attrgetter
from typing import overload

from pydantic import BaseModel, ConfigDict, Field, field_serializer
from sqlalchemy import Column, Integer, TIMESTAMP, TEXT, ForeignKey, Enum, event, inspect, select
# from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import relationship, joinedload
from sqlalchemy.exc import NoResultFound, MultipleResultsFound

from productionsystem.utils import timestamp

from ..enums import LocalStatus
from ..registry import managed_session
from ..SQLTableBase import SQLTableBase, SmartColumn
# Import the sibling model classes directly from their submodules (rather than via
# ``from ..models import ParametricJobs, Users``) so this always resolves to the class even if
# something elsewhere has already triggered a bare import of that submodule, which would
# otherwise leave the ``productionsystem.sql.models`` package attribute of the same name
# pointing at the raw module instead of the class.
from .ParametricJobs import ParametricJobs, ParametricJob
from .Users import Users, User


def subdict(dct, keys, **kwargs):
    """Create a sub dictionary."""
    out = {k: dct[k] for k in keys if k in dct}
    out.update(kwargs)
    return out


class Request(BaseModel):
    """JSON-serialisable schema for a Requests row."""

    model_config = ConfigDict(from_attributes=True, validate_assignment=True)

    id: int = Field(frozen=True)
    description: str
    requester_id: int
    request_date: datetime
    status: LocalStatus
    timestamp: datetime
    log: str
    parametric_jobs: list[ParametricJob] = Field(default_factory=list)
    requester: User

    @field_serializer("status")
    def _serialize_status(self, value: LocalStatus) -> str:
        return value.name.capitalize()

    @field_serializer("request_date", "timestamp")
    def _serialize_datetime(self, value: datetime) -> str:
        return value.isoformat(' ')


class Requests(SQLTableBase):
    """Requests SQL Table."""

    __tablename__ = 'requests'
    classtype = Column(TEXT)
    __mapper_args__ = {'polymorphic_on': classtype,
                       'polymorphic_identity': 'requests',
                       'with_polymorphic': '*'}
    id = Column(Integer, primary_key=True)  # pylint: disable=invalid-name
    description = SmartColumn(TEXT, nullable=True, allowed=True)
    requester_id = SmartColumn(Integer, ForeignKey('users.id'), nullable=False, required=True)
    request_date = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc))
    status = Column(Enum(LocalStatus), nullable=False, default=LocalStatus.REQUESTED)
    timestamp = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    log = Column(TEXT, nullable=False, default="")
    parametric_jobs = relationship("ParametricJobs", cascade="all, delete-orphan")
    requester = relationship(Users)
    logger = logging.getLogger(__name__).getChild(__qualname__)

    def __init__(self, **kwargs):
        """Initialise."""
        required_args = set(self.required_columns).difference(kwargs)
        if required_args:
            raise ValueError("Missing required keyword args: %s" % list(required_args))
        super().__init__(**subdict(kwargs, self.allowed_columns))
        parametricjobs = kwargs.get('parametricjobs', [])
        if not parametricjobs:
            self._clientlog("No parametricjobs associated with new request.")
            self.logger.warning("No parametricjobs associated with new request.")
        for job_id, parametricjob in enumerate(parametricjobs):
            parametricjob.pop('requester_id', None)
            parametricjob.pop('request_id', None)
            parametricjob.pop('id', None)
            try:
                self.parametric_jobs.append(ParametricJobs(request_id=self.id, id=job_id + 1,
                                                           requester_id=self.requester_id,
                                                           **parametricjob))
            except ValueError:
                self._clientlog("Error creating parametricjob, bad input: %s" % parametricjob)
                self.logger.exception("Error creating parametricjob, bad input: %s", parametricjob)
                raise

    def _clientlog(self, log):
        if self.log is None:
            self.log = ''
        self.log += "%s %s\n" % (timestamp(), log)

    def add(self):
        """Add self to the DB."""
        with managed_session() as session:
            session.add(self)
            session.flush()
            session.refresh(self)

    def remove(self):
        """Remove self from the DB."""
        with managed_session() as session:
            session.delete(self)

    def update(self):
        """Update the DB with current values."""
        with managed_session() as session:
            session.merge(self)

    def submit(self):
        """Submit Request."""
        self._clientlog("Submitting request %s" % self.id)
        self.logger.info("Submitting request %s", self.id)
        try:
            for job in self.parametric_jobs:  # pyright: ignore[reportGeneralTypeIssues]
                job.submit()
        except BaseException as err:
            self._clientlog("Unhandled exception while submitting request\n%s" % err)
            self.logger.exception("Unhandled exception while submitting request %s", self.id)
            self.status = LocalStatus.FAILED

    def monitor(self):
        """Update request status."""
        self.logger.info("Monitoring request %s", self.id)
        if not self.parametric_jobs:
            self._clientlog("No parametric jobs present to monitor, changing status to Unknown")
            self.logger.warning("No parametric jobs associated with request: %d. "
                                "returning status unknown", self.id)
            self.status = LocalStatus.UNKNOWN
            return

        status = LocalStatus.UNKNOWN
        for job in self.parametric_jobs:  # pyright: ignore[reportGeneralTypeIssues]
            try:
                job.monitor()
            # get rid of this if parametricjob catches everything. Only when sure as it's complex
            except BaseException as err:
                self._clientlog("Unhandled exception monitoring ParametricJob %s\n%s" % (job.id, err))
                self.logger.exception("Unhandled exception monitoring ParametricJob %s", job.id)
                job.status = LocalStatus.UNKNOWN
            status = max(status, job.status)

        if status != self.status:
            self.status = status

    @classmethod
    def delete(cls, request_id: int):
        """Delete a requests from the DB."""
        try:
            request_id = int(request_id)
        except ValueError:
            cls.logger.error("Request id: %r should be of type int "
                             "(or convertable to int)", request_id)
            raise

        with managed_session() as session:
            try:
                request = session.scalars(
                    select(cls)
                    .where(cls.id == request_id)
                    ).one()
            except NoResultFound:
                cls.logger.warning("No result found for request id: %d", request_id)
                raise
            except MultipleResultsFound:
                cls.logger.error("Multiple results found for request id: %d", request_id)
                raise
            session.delete(request)
            cls.logger.info("Request %d deleted.", request_id)


    @overload
    @classmethod
    def get(cls,
            *,
            load_user: bool = False,
            load_parametricjobs: bool = False) -> list[Requests]: ...

    @overload
    @classmethod
    def get(cls,
            *,
            request_id: list[int],
            load_user: bool = False, load_parametricjobs: bool = False) -> list[Requests]: ...

    @overload
    @classmethod
    def get(cls,
            *,
            request_id: int,
            load_user: bool = False,
            load_parametricjobs: bool = False) -> Requests: ...

    @overload
    @classmethod
    def get(cls,
            *,
            user_id: int,
            load_user: bool = False,
            load_parametricjobs: bool = False) -> list[Requests]: ...

    @overload
    @classmethod
    def get(cls,
            *,
            status: list[str],
            load_user: bool = False,
            load_parametricjobs: bool = False) -> list[Requests]: ...

    @overload
    @classmethod
    def get(cls,
            *,
            user_id: int,
            status: list[str],
            load_user: bool = False,
            load_parametricjobs: bool = False) -> list[Requests]: ...

    @classmethod
    def get(cls,
            *,
            request_id: int | list[int] | None = None,
            user_id: int | None = None,
            status: list[str] | None = None,
            load_user: bool = False,
            load_parametricjobs: bool = False) -> Requests | list[Requests]:
        """
        Get requests from the database

        Get all requests from the database or explicitly those with a given request_id, user_id or status.
        
        Args:
            request_id (int | list[int] | None): request id/ids to extract. Defaults to None.
            user_id (int | None): user id to extract. Defaults to None.
            status (list[str] | None): status values to filter by. Defaults to None.
            load_user (bool): whether to load the user information. Defaults to False.
            load_parametricjobs (bool): whether to load the parametric jobs. Defaults to False.

        Raises:
            TypeError: if the provided arguments are of incorrect type.

        Returns:
            Requests | list[Requests]: the retrieved request(s) from the database.
        """

        if request_id is not None:
            try:
                if isinstance(request_id, (list, tuple)):
                    request_id = [int(i) for i in request_id]
                else:
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

        if status is not None:
            if not isinstance(status, (list, tuple)):
                cls.logger.error("Status: %r should be of type list/tuple", status)
                raise TypeError

        with managed_session() as session:
            stmt = select(cls)
            if load_user:
                stmt = stmt.options(joinedload(cls.requester, innerjoin=True))
            if load_parametricjobs:
                stmt = stmt.options(joinedload(cls.parametric_jobs)
                                    .joinedload(ParametricJobs.dirac_jobs))
            if user_id is not None:
                stmt = stmt.where(cls.requester_id == user_id)
            if status is not None:
                stmt = stmt.where(cls.status.in_(status))  # pyright: ignore[reportAttributeAccessIssue]

            if request_id is None:
                requests = session.execute(stmt).unique().scalars().all()
                requests.sort(key=attrgetter('id'))
                return requests

            if isinstance(request_id, (list, tuple)):
                requests = session.execute(
                    stmt.where(cls.id.in_(request_id))
                ).unique().scalars().all()
                requests.sort(key=attrgetter('id'))
                return requests

            try:
                request = session.execute(
                    stmt.where(cls.id == request_id)
                ).unique().scalar_one()
            except NoResultFound:
                cls.logger.warning("No result found for request id: %d", request_id)
                raise
            except MultipleResultsFound:
                cls.logger.error("Multiple results found for request id: %d", request_id)
                raise
            return request

    @classmethod
    def get_reschedules(cls):
        """Get Requests with ParametricJobs to reschedule."""
        with managed_session() as session:
            requests = session.execute(
                select(cls)
                .options(joinedload(cls.parametric_jobs).joinedload(ParametricJobs.dirac_jobs))
                .where(cls.status == LocalStatus.FAILED)
                .join(cls.parametric_jobs)
                .where(ParametricJobs.reschedule is True)  # reschedule comes from joining the parametricjobs table.
            ).unique().scalars().all()
            return requests


@event.listens_for(Requests.status, "set", propagate=True)
def intercept_status_set(target, newvalue, oldvalue, _):
    """Intercept status transitions."""
    # will catch updates in detached state and again when we merge it into session
    if not inspect(target).detached and oldvalue != newvalue:
        target._clientlog("Request %d transitioned from status %s to %s" % (target.id, oldvalue.name, newvalue.name))
        target.logger.info("Request %d transitioned from status %s to %s",
                           target.id, oldvalue.name, newvalue.name)
