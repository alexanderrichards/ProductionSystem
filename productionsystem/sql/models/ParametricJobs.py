"""
ParametricJobs Table.
"""
from __future__ import annotations

import logging
import os
from collections import Counter, defaultdict
from collections.abc import Iterable
from copy import deepcopy
from datetime import datetime, timezone
from operator import attrgetter
from typing import TYPE_CHECKING, overload
if TYPE_CHECKING:
    from io import TextIOWrapper

from pydantic import BaseModel, ConfigDict, Field, field_serializer
from sqlalchemy import (TEXT,
                        TIMESTAMP,
                        Boolean,
                        CheckConstraint,
                        Enum,
                        ForeignKey,
                        Integer,
                        SmallInteger,
                        event,
                        inspect,
                        select)
from sqlalchemy.exc import MultipleResultsFound, NoResultFound
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from productionsystem.config import getConfig
from productionsystem.monitoring.diracrest.DiracRESTClient import dirac_api_client,dirac_api_job_client
from productionsystem.utils import TemporaryFileManagerContext, igroup, timestamp
if TYPE_CHECKING:
    from productionsystem.monitoring.diracrest.DiracRESTClient import DiracAPIJobClass

from ..enums import DiracStatus, LocalStatus
from ..registry import managed_session
from ..SQLTableBase import SQLTableBase
from .DiracJobs import DiracJobs


class ParametricJob(BaseModel):
    """
    JSON-serialisable schema for a ParametricJobs row.
    """
    model_config = ConfigDict(from_attributes=True, validate_assignment=True)

    request_id: int = Field(frozen=True)
    id: int = Field(frozen=True)
    requester_id: int = Field(frozen=True)
    priority: int = Field(frozen=True)
    site: str = Field(frozen=True)
    status: LocalStatus = Field(frozen=True)
    reschedule: bool = Field(frozen=True)
    timestamp: datetime = Field(frozen=True)
    num_jobs: int = Field(frozen=True)
    num_completed: int = Field(frozen=True)
    num_failed: int = Field(frozen=True)
    num_submitted: int = Field(frozen=True)
    num_running: int = Field(frozen=True)
    log: str = Field(frozen=True)

    @field_serializer("status")
    def _serialize_status(self, value: LocalStatus) -> str:
        """
        Serialize a local status enum using its display name.
        
        Args:
            value: Local status enum value from the model field.

        Returns:
            str: Capitalized local status name for API responses.
        """
        return value.name.capitalize()

    @field_serializer("timestamp")
    def _serialize_timestamp(self, value: datetime) -> str:
        """
        Serialize a timestamp in the API's string representation.
        
        Args:
            value: Job timestamp from the model field.

        Returns:
            str: UTC ISO-like timestamp string for API responses.
        """
        if value.tzinfo is None:
            # Database returned a naive value as not all are timezone-aware; this assumes it was stored as UTC.
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)

        return value.isoformat(" ")

class ParametricJobCreate(BaseModel):
    """
    Input schema for creating a parametric job with a request.
    """
    priority: int = 3
    site: str = "ANY"


class ParametricJobs(SQLTableBase):
    """
    Jobs SQL Table.
    """
    __tablename__ = 'parametricjobs'
    classtype: Mapped[str] = mapped_column(TEXT)
    __mapper_args__ = {'polymorphic_on': classtype,
                       'polymorphic_identity': 'parametricjobs',
                       'with_polymorphic': '*'}
    request_id: Mapped[int] = mapped_column(Integer, ForeignKey('requests.id'), primary_key=True)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # pylint: disable=invalid-name
    requester_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False)
    priority: Mapped[int] = mapped_column(SmallInteger, CheckConstraint('priority >= 0 and priority < 10'),
                           nullable=False, default=3)
    site: Mapped[str] = mapped_column(TEXT, nullable=False, default='ANY')
    status: Mapped[LocalStatus] = mapped_column(Enum(LocalStatus), nullable=False, default=LocalStatus.REQUESTED)
    reschedule: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    timestamp: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    num_jobs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    num_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    num_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    num_submitted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    num_running: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    log: Mapped[str] = mapped_column(TEXT, nullable=False, default="")
    dirac_jobs: Mapped[list[DiracJobs]] = relationship("DiracJobs", cascade="all, delete-orphan",
                                                         primaryjoin="and_(ParametricJobs.request_id==DiracJobs.request_id, "
                                                                     "ParametricJobs.id==DiracJobs.parametricjob_id)")
    logger = logging.getLogger(__name__).getChild(__qualname__)

    @hybrid_property
    def num_other(self) -> int:
        """
        Return the number of jobs in states other than the known ones.

        Returns:
            int: Jobs not counted as submitted, running, failed, or completed.
        """
        return self.num_jobs - (self.num_submitted +
                                self.num_running +
                                self.num_failed +
                                self.num_completed)

    def update(self):
        """
        Update DB with current values.
        """
        with managed_session() as session:
            session.merge(self)

    def _clientlog(self, log: str):
        """
        Append a message to the job's client-visible log.
        
        Args:
            log: Message to append to the parametric job log with a timestamp.
        """
        if self.log is None:
            self.log = ''
        self.log += "%s %s\n" % (timestamp(), log)

    def _remove_dirac_jobs(self):
        """
        Remove dirac_jobs from the DIRAC system.

        Returns:
            None. Removes associated DIRAC jobs when present and logs cleanup failures.
        """
        if not self.dirac_jobs:
            return

        dirac_ids = {job.id for job in self.dirac_jobs}
        for ids in igroup(dirac_ids, 1000):
            try:
                with dirac_api_client() as dirac:
                    self.logger.info("Killing/deleting %d DIRAC job(s).", len(ids))
                    dirac.killJob(ids)
                    dirac.deleteJob(ids)
            except BaseException:
                self.logger.exception("Error doing DIRAC tidy up of %d job(s). Cleaning up local "
                                      "system and forgetting about the (possibly) orphaned jobs "
                                      "on DIRAC system", len(ids))

#    @abstractmethod
    def _setup_dirac_job(self,
                         DiracJobClass: DiracAPIJobClass,
                         tmp_runscript: TextIOWrapper,
                         tmp_filemanager: TemporaryFileManagerContext):
        """
        Define the DIRAC parametric job.

        Args:
            DiracJobClass: Recorder class used to build DIRAC job definitions.
            tmp_runscript: Writable temporary shell script included in the DIRAC job sandbox.
            tmp_filemanager: Context manager for additional temporary job files.

        Returns:
            list[DiracAPIJob]: Recorded DIRAC job definitions to submit.
        """
        tmp_runscript.write("echo HelloWorld\n")
        tmp_runscript.flush()
        job = DiracJobClass()
        job.setName("Test DIRAC Job")
        job.setExecutable(os.path.basename(tmp_runscript.name))
        return [job]

    def submit(self):
        """
        Submit parametric job.

        Returns:
            None. Submits DIRAC jobs, records created IDs, and updates counters/status on failure.
        """
        with (dirac_api_job_client() as (dirac, dirac_job_class),
              TemporaryFileManagerContext() as tmp_filemanager,
              open(os.path.join(tmp_filemanager.new_dir(), "runscript.sh"), "w") as tmp_runscript):
            os.chmod(tmp_runscript.name, 0o755)
            try:
                dirac_jobs = self._setup_dirac_job(dirac_job_class,
                                                   tmp_runscript,
                                                   tmp_filemanager)
            except Exception as err:
                self._clientlog("Error setting up DIRAC jobs for parametric job %d.%d"
                                % (self.request_id, self.id))
                self.logger.exception("Error setting up DIRAC jobs for the parametric job %d.%d: %s",
                                      self.request_id, self.id, err)
                self.status = LocalStatus.FAILED
                return

            if not isinstance(dirac_jobs, Iterable):
                dirac_jobs = [dirac_jobs]

            # If the parametricjob has large number of subjobs then submission could timeout
            # waiting for DIRAC to create all the subjobs, this allows you to split it into
            # a few parametricjobs.
            dirac_job_ids = set()

            if not dirac_jobs:
                self._clientlog("No DIRAC jobs were created so none to submit.")
                self.logger.warning("No DIRAC jobs were created so none to submit.")

            for dirac_job in dirac_jobs:
                try:
                    result = dirac.submitJob(dirac_job)
                except Exception as err:
                    self._clientlog("Error submitting parametric job %d.%d using DIRAC API"
                                    % (self.request_id, self.id))
                    self.logger.exception("Error submitting parametric job %d.%d: %s",
                                          self.request_id, self.id, err)
                    self.status = LocalStatus.FAILED
                    self._remove_dirac_jobs()  # Clean up Dirac jobs that may have been created
                    return

                if not result['OK']:
                    self._clientlog("DIRAC error submitting parametricjob %d.%d"
                                    % (self.request_id, self.id))
                    self.logger.error("DIRAC error submitting parametricjob %d.%d: %s",
                                      self.request_id, self.id, result['Message'])
                    self.status = LocalStatus.FAILED
                    self._remove_dirac_jobs()  # Clean up Dirac jobs that may have been created
                    return

                created_ids = result['Value']
                if isinstance(created_ids, int):  # non-parametric submission
                    created_ids = [created_ids]
                dirac_job_ids.update(created_ids)

            if not dirac_job_ids:
                self._clientlog("DIRAC job submit API returned not job ids.")
                self.logger.warning("DIRAC job submit API returned not job ids.")

            self.dirac_jobs = [DiracJobs(id=i, parametricjob_id=self.id, request_id=self.request_id,
                                         requester_id=self.requester_id,
                                         status=DiracStatus.RECEIVED) for i in dirac_job_ids]
            self.num_jobs = len(self.dirac_jobs)
            if self.num_jobs:
                self._clientlog("Successfully submitted %d Dirac jobs for %d.%d"
                                % (self.num_jobs, self.request_id, self.id))
                self.logger.info("Successfully submitted %d Dirac jobs for %d.%d",
                                 self.num_jobs, self.request_id, self.id)

    def monitor(self):
        """
        Bulk update status.

        This method updates all DIRAC jobs which belong to the given
        parametricjob.

        Returns:
            None. Refreshes DIRAC job statuses, reschedules jobs when needed, and updates counters.
        """
        # Group jobs by status

        if self.status not in (LocalStatus.APPROVED,
                               LocalStatus.REQUESTED,
                               LocalStatus.SUBMITTED,
                               LocalStatus.SUBMITTING,
                               LocalStatus.RUNNING,
                               LocalStatus.REMOVING):
            self.logger.debug("Not monitoring parametric job %d.%d as state %r", self.request_id, self.id, self.status)
            return

        if not self.dirac_jobs:
            self._clientlog("No dirac jobs associated with this parametricjob. returning status UNKNOWN")
            self.logger.warning("No dirac jobs associated with parametricjob: "
                                "%d.%d. returning status UNKNOWN",
                                self.request_id, self.id)
            self.status = LocalStatus.UNKNOWN
            self.reschedule = False
            self.num_completed = 0
            self.num_failed = 0
            self.num_submitted = 0
            self.num_running = 0
            return

        num_reschedules = getConfig("parametricjobs").get("reschedules", 2)
        job_types: defaultdict[DiracStatus, set[int]] = defaultdict(set)
        for job in self.dirac_jobs:
            job_types[job.status].add(job.id)
            # add auto-reschedule jobs
            if job.status in (DiracStatus.FAILED, DiracStatus.STALLED) and job.reschedules < num_reschedules:
                # Note: RESCHEDULED status is used for counting only and is never applied to the actual job status
                job_types[DiracStatus.RESCHEDULED].add(job.id)

        reschedule_jobs: set[int] = job_types[DiracStatus.RESCHEDULED] if job_types[DiracStatus.DONE] else set()
        monitor_jobs: set[int] = (job_types[DiracStatus.RUNNING]
                                  | job_types[DiracStatus.RECEIVED]
                                  | job_types[DiracStatus.QUEUED]
                                  | job_types[DiracStatus.WAITING]
                                  | job_types[DiracStatus.CHECKING]
                                  | job_types[DiracStatus.MATCHED]
                                  | job_types[DiracStatus.UNKNOWN]
                                  | job_types[DiracStatus.COMPLETED]
                                  | job_types[DiracStatus.COMPLETING])

        if self.reschedule:  # Manually triggered reschedule of all failed/stalled from Web app
            reschedule_jobs = job_types[DiracStatus.FAILED] | job_types[DiracStatus.STALLED]

        # Reschedule jobs
        rescheduled_jobs = set()
        if reschedule_jobs:
            self._clientlog("Rescheduling DIRAC jobs: %s" % list(reschedule_jobs))
            self.logger.info("Rescheduling DIRAC jobs: %s", list(reschedule_jobs))
            with dirac_api_client() as dirac:
                try:
                    result = dirac.rescheduleJob(reschedule_jobs)
                except Exception as err:
                    self._clientlog("Error calling DIRAC to reschedule jobs: %s" % err)
                    self.logger.exception("Error calling DIRAC to reschedule jobs: %s", err)
                else:
                    if not result['OK']:
                        self._clientlog("DIRAC failed to reschedule jobs: %s" % result['Message'])
                        self.logger.error("DIRAC failed to reschedule jobs: %s", result['Message'])
                    else:
                        rescheduled_jobs.update(result['Value'])
                        self._clientlog("Rescheduled jobs: %s" % list(rescheduled_jobs))
                        self.logger.info("Rescheduled jobs: %s", list(rescheduled_jobs))
                        skipped_jobs = reschedule_jobs.difference(rescheduled_jobs)
                        if skipped_jobs:
                            self._clientlog("Failed to reschedule jobs: %s" % list(skipped_jobs))
                            self.logger.warning("Failed to reschedule jobs: %s", list(skipped_jobs))
                        monitor_jobs.update(rescheduled_jobs)

        # Update status
        monitored_jobs = {}
        self.logger.debug("Monitoring DIRAC jobs: %s", list(monitor_jobs))
        if monitor_jobs:
            try:
                with dirac_api_client() as dirac:
                    dirac_answer = deepcopy(dirac.getJobStatus(monitor_jobs))
            except Exception as err:
                self._clientlog("Error calling DIRAC to monitor jobs: %s" % err)
                self.logger.exception("Error calling DIRAC to monitor jobs: %s", err)
            else:
                if not dirac_answer['OK']:
                    self._clientlog("DIRAC failed to get statuses for jobs belonging to this parametricjob: %s"
                                    % dirac_answer['Message'])
                    self.logger.error("DIRAC failed to get statuses for jobs belonging to "
                                      "parametricjob id %d.%d: %s",
                                      self.request_id, self.id, dirac_answer['Message'])
                    self.reschedule = False
                else:
                    monitored_jobs = dirac_answer['Value']
                    skipped_jobs = monitor_jobs.difference(monitored_jobs)
                    if skipped_jobs:
                        self._clientlog("Couldn't check the status of jobs: %s" % list(skipped_jobs))
                        self.logger.warning("Couldn't check the status of jobs: %s",
                                            list(skipped_jobs))

        statuses = Counter()
        for job in self.dirac_jobs:  # pyright: ignore[reportGeneralTypeIssues]
            if job.id in rescheduled_jobs:
                job.reschedules += 1
            if job.id in monitored_jobs:
                try:
                    # pylint: disable=unsubscriptable-object
                    job.status = DiracStatus[monitored_jobs[job.id]['Status'].upper()]
                except KeyError:
                    self._clientlog("Unknown DiracStatus: %s. Setting to UNKNOWN"
                                    % monitored_jobs[job.id]['Status'].upper())
                    self.logger.warning("Unknown DiracStatus: %s. Setting to UNKNOWN",
                                        monitored_jobs[job.id]['Status'].upper())
                    job.status = DiracStatus.UNKNOWN
            if not isinstance(job.status, DiracStatus):
                self._clientlog("Dirac job %r status %r is invalid type %r"
                                % (str(job.id), job.status, type(job.status)))
                self.logger.error("Dirac job %r status %r is invalid type %r",
                                  str(job.id), job.status, type(job.status))
                job.status = DiracStatus.RUNNING
            statuses.update((job.status.local_status,))

        status = max(statuses)
        if status != self.status:
            self.status = status

        self.num_completed = statuses[LocalStatus.COMPLETED]
        self.num_failed = statuses[LocalStatus.FAILED]
        self.num_submitted = statuses[LocalStatus.SUBMITTED]
        self.num_running = statuses[LocalStatus.RUNNING]
        self.reschedule = False

    @overload
    @classmethod
    def get(cls) -> list[ParametricJobs]: ...

    @overload
    @classmethod
    def get(cls, *, request_id:int) -> list[ParametricJobs]: ...

    @overload
    @classmethod
    def get(cls, *, parametricjob_id:int) -> list[ParametricJobs]: ...

    @overload
    @classmethod
    def get(cls, *, user_id:int) -> list[ParametricJobs]: ...

    @overload
    @classmethod
    def get(cls, *, request_id:int, user_id:int) -> list[ParametricJobs]: ...

    @overload
    @classmethod
    def get(cls, *, request_id:int, user_id: None) -> list[ParametricJobs]: ...

    @overload
    @classmethod
    def get(cls, *, parametricjob_id:int, user_id:int) -> list[ParametricJobs]: ...

    @overload
    @classmethod
    def get(cls, *, request_id:int, parametricjob_id:int) -> ParametricJobs: ...

    @overload
    @classmethod
    def get(cls, *, request_id:int, parametricjob_id:int, user_id:int) -> ParametricJobs: ...

    @overload
    @classmethod
    def get(cls, *, request_id:int, parametricjob_id:int, user_id: None) -> ParametricJobs: ...

    @classmethod
    def get(cls,
            *,
            request_id: int | None = None,
            parametricjob_id: int | None = None,
            user_id: int | None = None) -> ParametricJobs | list[ParametricJobs]:
        """
        Get parametricjobs from the database.

        Gets all parametricjobs in database or explicitly those with a given request_id, parametricjob_id  or user_id.

        Args:
            request_id (int | None): request id to extract. Defaults to None.
            parametricjob_id (int | None): parametricjob id to extract. Defaults to None.
            user_id (int | None): user id to extract. Defaults to None.

        Raises:
            TypeError: If request_id, parametricjob_id, or user_id is not an int (or convertable to int).
            NoResultFound: If no parametricjob matches the given criteria when a request_id and parametricjob_id
                           is provided.
            MultipleResultsFound: If multiple parametricjobs match the given criteria when a request_id and
                                  parametricjob_id is provided.

        Returns:
            ParametricJobs | list[ParametricJobs]: The parametricjob/parametricjobs pulled from the database
        """
        if request_id is not None:
            try:
                request_id = int(request_id)
            except ValueError as err:
                cls.logger.error("Request id: %r should be of type int (or convertable to int)", request_id)
                raise TypeError(f"Request id: {request_id!r} should be of type int (or convertable to int)") from err

        if parametricjob_id is not None:
            try:
                parametricjob_id = int(parametricjob_id)
            except ValueError as err:
                cls.logger.error("Parametric job id: %r should be of type int (or convertable to int)",
                                 parametricjob_id)
                raise TypeError(f"Parametric job id: {parametricjob_id!r} should be of type int "
                                "(or convertable to int)") from err

        if user_id is not None:
            try:
                user_id = int(user_id)
            except ValueError as err:
                cls.logger.error("User id: %r should be of type int (or convertable to int)", user_id)
                raise TypeError(f"User id: {user_id!r} should be of type int (or convertable to int)") from err

        with managed_session() as session:
            stmt = select(cls)
            if request_id is not None:
                stmt = stmt.where(cls.request_id == request_id)
            if parametricjob_id is not None:
                stmt = stmt.where(cls.id == parametricjob_id)
            if user_id is not None:
                stmt = stmt.where(cls.requester_id == user_id)

            # TODO: Check this is correct, maybe should be just parametricjob_id
            if request_id is None or parametricjob_id is None:
                parametricjobs = session.scalars(stmt).all()
                parametricjobs.sort(key=attrgetter("id"))
                return parametricjobs

            try:
                parametricjob = session.scalars(stmt).one()
            except NoResultFound:
                cls.logger.warning("No result found for parametric job id: %d", parametricjob_id)
                raise
            except MultipleResultsFound:
                cls.logger.error("Multiple results found for parametric job id: %d", parametricjob_id)
                raise
            return parametricjob


@event.listens_for(ParametricJobs.status, "set", propagate=True)
def intercept_status_set(target, newvalue, oldvalue, _):
    """
    Intercept status transitions.

    Args:
        target: Parametric job whose status is being changed.
        newvalue: New local status assigned to the parametric job.
        oldvalue: Previous local status before the assignment.
        _: SQLAlchemy event initiator, unused.
    """
    # will catch updates in detached state and again when we merge it into session
    if not inspect(target).detached and oldvalue != newvalue:
        target._clientlog("Parametric job %d.%d transitioned from status %s to %s"
                          % (target.request_id, target.id, oldvalue.name, newvalue.name))
        target.logger.info("Parametric job %d.%d transitioned from status %s to %s",
                           target.request_id, target.id, oldvalue.name, newvalue.name)


@event.listens_for(Session, "persistent_to_deleted")
def intercept_persistent_to_deleted(session, object_):
    """
    Intercept deletion of object and remove DIRAC jobs.

    Args:
        session: SQLAlchemy session emitting the deletion transition.
        object_: Persistent ORM object being deleted.
    """
    if isinstance(object_, DiracJobs):
        DiracJobs.logger.debug("Local DB Dirac job %d from parametric job %d.%d is being removed.",
                               object_.id, object_.request_id, object_.parametricjob_id)

    if isinstance(object_, ParametricJobs):
        ParametricJobs.logger.info("Parametric job %d.%d is being removed, triggering bulk tidy up "
                                   "of DIRAC job(s).",
                                   object_.request_id, object_.id)
        object_._remove_dirac_jobs()
