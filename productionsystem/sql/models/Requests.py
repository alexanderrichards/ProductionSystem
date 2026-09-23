"""Requests Table."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from operator import attrgetter
from typing import overload

from pydantic import BaseModel, ConfigDict, Field, field_serializer
from sqlalchemy import TEXT, TIMESTAMP, Enum, ForeignKey, Integer, event, inspect, select
from sqlalchemy.exc import MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Mapped, joinedload, mapped_column, relationship

from productionsystem.utils import timestamp
from ..enums import LocalStatus
from ..registry import managed_session
from ..SQLTableBase import SQLTableBase
from . import ParametricJob, ParametricJobCreate, ParametricJobs
from .Users import User, Users


class Request(BaseModel):
    """JSON-serialisable schema for a Requests row."""

    model_config = ConfigDict(from_attributes=True, validate_assignment=True)

    id: int = Field(frozen=True)
    description: str = Field(frozen=True)
    requester_id: int = Field(frozen=True)
    request_date: datetime = Field(frozen=True)
    status: LocalStatus = Field(frozen=True)
    timestamp: datetime = Field(frozen=True)
    log: str = Field(frozen=True)
    parametric_jobs: list[ParametricJob] = Field(default_factory=list, frozen=True)
    requester: User = Field(frozen=True)

    @field_serializer("status")
    def _serialize_status(self, value: LocalStatus) -> str:
        return value.name.capitalize()

    @field_serializer("request_date", "timestamp")
    def _serialize_datetime(self, value: datetime) -> str:
        if value.tzinfo is None:
            # Database returned a naive value as not all are timezone-aware; this assumes it was stored as UTC.
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)

        return value.isoformat(" ")


class RequestCreate(BaseModel):
    """Input schema for creating a request and its parametric jobs."""

    description: str = ""
    parametric_jobs: list[ParametricJobCreate] = Field(default_factory=list)


class Requests(SQLTableBase):
    """Requests SQL Table."""

    __tablename__ = 'requests'
    classtype: Mapped[str] = mapped_column(TEXT)
    __mapper_args__ = {'polymorphic_on': classtype,
                       'polymorphic_identity': 'requests',
                       'with_polymorphic': '*'}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # pylint: disable=invalid-name
    description: Mapped[str] = mapped_column(TEXT, nullable=True)
    requester_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False)
    request_date: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc))
    status: Mapped[LocalStatus] = mapped_column(Enum(LocalStatus), nullable=False, default=LocalStatus.REQUESTED)
    timestamp: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    log: Mapped[str] = mapped_column(TEXT, nullable=False, default="")
    parametric_jobs: Mapped[list[ParametricJobs]] = relationship("ParametricJobs", cascade="all, delete-orphan")
    requester: Mapped[Users] = relationship(Users)
    logger = logging.getLogger(__name__).getChild(__qualname__)


    def _clientlog(self, log: str):
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


    # TODO: make sure pydantic model validation errors propagate to client.
    @classmethod
    def create(cls, *, requester_id: int, validated_request_data: RequestCreate) -> Requests:
        """
        Create new request in DB.

        Args:
            requester_id (int): The id of the requester.
            validated_request_data (RequestCreate): New request data.

        Raises:
            ValueError: If there is an error creating parametric jobs due to bad input.

        Returns:
            Requests: The newly created request object.
        """
        try:
            parametricjobs = [
                ParametricJobs(
                    id=job_id,
                    requester_id=requester_id,
                    **job_values.model_dump(),
                )
                for job_id, job_values in enumerate(validated_request_data.parametric_jobs, start=1)
            ]
        except Exception as err:
            cls.logger.exception("Error creating parametric jobs, bad input: %s\n%s",
                                 err,
                                 validated_request_data.model_dump())
            raise ValueError("Error creating parametric jobs, bad input") from err 

        request = cls(
            requester_id=requester_id,
            **(validated_request_data.model_dump() | {"parametric_jobs": parametricjobs}),
        )

        if not parametricjobs:
            request._clientlog("No parametricjobs associated with new request.")
            cls.logger.warning("No parametricjobs associated with new request.")

        with managed_session() as session:
            session.add(request)
            session.flush()
            session.refresh(request)

        return request


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
            user_id: None,
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
            request_id: int,
            user_id: int,
            load_user: bool = False,
            load_parametricjobs: bool = False) -> Requests: ...

    @overload
    @classmethod
    def get(cls,
            *,
            request_id: int,
            user_id: None,
            load_user: bool = False,
            load_parametricjobs: bool = False) -> Requests: ...

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
            NoResultFound: If no request matches the given criteria when integer request_id is provided.
            MultipleResultsFound: If multiple requests match the given criteria when integer request_id is provided.

        Returns:
            Requests | list[Requests]: the retrieved request(s) from the database.
        """

        if request_id is not None:
            try:
                if isinstance(request_id, (list, tuple)):
                    request_id = [int(i) for i in request_id]
                else:
                    request_id = int(request_id)
            except ValueError as err:
                cls.logger.error("Request id: %r should be of type int (or convertable to int)", request_id)
                raise TypeError(f"Request id: {request_id!r} should be of type int (or convertable to int).") from err

        if user_id is not None:
            try:
                user_id = int(user_id)
            except ValueError as err:
                cls.logger.error("User id: %r should be of type int (or convertable to int)", user_id)
                raise TypeError(f"User id: {user_id!r} should be of type int (or convertable to int).") from err

        if status is not None and not isinstance(status, (list, tuple)):
            cls.logger.error("Status: %r should be of type list/tuple", status)
            raise TypeError(f"Status: {status!r} should be of type list/tuple.")

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
                .where(ParametricJobs.reschedule == True)  # reschedule comes from joining the parametricjobs table.
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
