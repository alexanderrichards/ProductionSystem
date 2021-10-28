"""ParametricJobs Table."""
# Py2/3 compatibility layer
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *  # pylint: disable=wildcard-import, unused-wildcard-import, redefined-builtin

import os
import json
import logging
from abc import abstractmethod
from datetime import datetime
from collections import defaultdict, Counter, Iterable
from copy import deepcopy
from tempfile import NamedTemporaryFile
from operator import attrgetter

from future.utils import native
import cherrypy
from sqlalchemy import (Column, SmallInteger, Integer, Boolean, TEXT, TIMESTAMP,
                        ForeignKey, Enum, CheckConstraint, event, inspect)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from productionsystem.config import getConfig
from productionsystem.utils import TemporyFileManagerContext, igroup
from productionsystem.monitoring.diracrpc.DiracRPCClient import (dirac_api_client,
                                                                 dirac_api_job_client)
# from lzproduction.rpc.DiracRPCClient import dirac_api_client, ParametricDiracJobClient
from ..enums import LocalStatus, DiracStatus
from ..registry import managed_session, SessionRegistry
from ..SQLTableBase import SQLTableBase, SmartColumn
from ..models import DiracJobs


def subdict(dct, keys, **kwargs):
    """Create a sub dictionary."""
    out = {k: dct[k] for k in keys if k in dct}
    out.update(kwargs)
    return out


@cherrypy.expose
@cherrypy.popargs('parametricjob_id')
class ParametricJobs(SQLTableBase):
    """Jobs SQL Table."""

    __tablename__ = 'parametricjobs'
    classtype = Column(TEXT)
    __mapper_args__ = {'polymorphic_on': classtype,
                       'polymorphic_identity': 'parametricjobs',
                       'with_polymorphic': '*'}
    request_id = SmartColumn(Integer, ForeignKey('requests.id'), primary_key=True, required=True)
    id = SmartColumn(Integer, primary_key=True, required=True)  # pylint: disable=invalid-name
    requester_id = SmartColumn(Integer, ForeignKey('users.id'), required=True, nullable=False)
    priority = SmartColumn(SmallInteger, CheckConstraint('priority >= 0 and priority < 10'),
                           nullable=False, default=3, allowed=True)
    site = SmartColumn(TEXT, nullable=False, default='ANY', allowed=True)
    status = Column(Enum(LocalStatus), nullable=False, default=LocalStatus.REQUESTED)
    reschedule = Column(Boolean, nullable=False, default=False)
    timestamp = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    num_jobs = SmartColumn(Integer, nullable=False, default=0)
    num_completed = Column(Integer, nullable=False, default=0)
    num_failed = Column(Integer, nullable=False, default=0)
    num_submitted = Column(Integer, nullable=False, default=0)
    num_running = Column(Integer, nullable=False, default=0)
    dirac_jobs = relationship("DiracJobs", cascade="all, delete-orphan",
                              primaryjoin="and_(ParametricJobs.request_id==DiracJobs.request_id, "
                                          "ParametricJobs.id==DiracJobs.parametricjob_id)")
    logger = logging.getLogger(__name__)

    @hybrid_property
    def num_other(self):
        """Return the number of jobs in states other than the known ones."""
        return self.num_jobs - (self.num_submitted +
                                self.num_running +
                                self.num_failed +
                                self.num_completed)

    def __init__(self, **kwargs):
        """Initialise."""
        required_args = set(self.required_columns).difference(kwargs)  # pylint: disable=no-member
        if required_args:
            raise ValueError("Missing required keyword args: %s" % list(required_args))
        # pylint: disable=no-member
        super(ParametricJobs, self).__init__(**subdict(kwargs, self.allowed_columns))

    def update(self):
        """Update DB with current values."""
        with managed_session() as session:
            session.merge(self)

    def _remove_dirac_jobs(self):
        """Remove dirac_jobs from the DIRAC system."""
        if not self.dirac_jobs:
            return

        dirac_ids = [job.id for job in self.dirac_jobs]
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
    def _setup_dirac_job(self, DiracJob, tmp_runscript, tmp_filemanager):
        """Define the DIRAC parametric job."""
        tmp_runscript.write("echo HelloWorld\n")
        tmp_runscript.flush()
        job = DiracJob()
        job.setName("Test DIRAC Job")
        job.setExecutable(os.path.basename(tmp_runscript.name))
        return [job]

    def submit(self):
        """Submit parametric job."""
        with dirac_api_job_client() as (dirac, dirac_job_class),\
                TemporyFileManagerContext() as tmp_filemanager,\
                open(os.path.join(tmp_filemanager.new_dir(), "runscript.sh"), "w") as tmp_runscript:
            os.chmod(tmp_runscript.name, 0o755)
            try:
                dirac_jobs = self._setup_dirac_job(dirac_job_class,
                                                   tmp_runscript,
                                                   tmp_filemanager)
            except Exception as err:
                self.logger.exception("Error setting up the parametric job %d.%d: %s",
                                      self.request_id, self.id, err)
                self.status = LocalStatus.FAILED
                return

            if not isinstance(dirac_jobs, Iterable):
                dirac_jobs = [dirac_jobs]

            # If the parametricjob has large number of subjobs then submission could timeout
            # waiting for DIRAC to create all the subjobs, this allows you to split it into
            # a few parametricjobs.
            dirac_job_ids = set()
            for dirac_job in dirac_jobs:
                try:
                    result = dirac.submitJob(dirac_job)
                except Exception as err:
                    self.logger.exception("Error submitting parametric job %d.%d: %s",
                                          self.request_id, self.id, err)
                    self.status = LocalStatus.FAILED
                    self._remove_dirac_jobs()  # Clean up Dirac jobs that may have been created
                    return

                if not result['OK']:
                    self.logger.error("DIRAC error submitting parametricjob %d.%d: %s",
                                      self.request_id, self.id, result['Message'])
                    self.status = LocalStatus.FAILED
                    self._remove_dirac_jobs()  # Clean up Dirac jobs that may have been created
                    return

                created_ids = result['Value']
                if isinstance(created_ids, int):  # non-parametric submission
                    created_ids = [created_ids]
                dirac_job_ids.update(created_ids)

            self.dirac_jobs = [DiracJobs(id=i, parametricjob_id=self.id, request_id=self.request_id,
                                         requester_id=self.requester_id,
                                         status=DiracStatus.UNKNOWN) for i in dirac_job_ids]
            self.num_jobs = len(self.dirac_jobs)
            self.logger.info("Successfully submitted %d Dirac jobs for %d.%d",
                             self.num_jobs, self.request_id, self.id)

    def monitor(self):
        """
        Bulk update status.

        This method updates all DIRAC jobs which belong to the given
        parametricjob.
        """
        # Group jobs by status

        if not self.dirac_jobs:
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
        job_types = defaultdict(set)
        for job in self.dirac_jobs:
            job_types[job.status].add(job.id)
            # add auto-reschedule jobs
            if job.status in (DiracStatus.FAILED, DiracStatus.STALLED) and\
                    job.reschedules < num_reschedules:
                job_types['Reschedule'].add(job.id)

        reschedule_jobs = job_types['Reschedule'] if job_types[DiracStatus.DONE] else set()
        monitor_jobs = job_types[DiracStatus.RUNNING] | \
            job_types[DiracStatus.RECEIVED] | \
            job_types[DiracStatus.QUEUED] | \
            job_types[DiracStatus.WAITING] | \
            job_types[DiracStatus.CHECKING] | \
            job_types[DiracStatus.MATCHED] | \
            job_types[DiracStatus.UNKNOWN] | \
            job_types[DiracStatus.COMPLETED] | \
            job_types[DiracStatus.COMPLETING]

        if self.reschedule:
            reschedule_jobs = job_types[DiracStatus.FAILED] | job_types[DiracStatus.STALLED]

        # Reschedule jobs
        rescheduled_jobs = set()
        if reschedule_jobs:
            self.logger.info("Rescheduling DIRAC jobs: %s", list(reschedule_jobs))
            with dirac_api_client() as dirac:
                try:
                    result = dirac.rescheduleJob(reschedule_jobs)
                except Exception as err:
                    self.logger.exception("Error calling DIRAC to reschedule jobs: %s", err)
                else:
                    if not result['OK']:
                        self.logger.error("DIRAC failed to reschedule jobs: %s", result['Message'])
                    else:
                        rescheduled_jobs.update(result['Value'])
                        self.logger.info("Rescheduled jobs: %s", list(rescheduled_jobs))
                        skipped_jobs = reschedule_jobs.difference(rescheduled_jobs)
                        if skipped_jobs:
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
                self.logger.exception("Error calling DIRAC to monitor jobs: %s", err)
            else:
                if not dirac_answer['OK']:
                    self.logger.error("DIRAC failed to get statuses for jobs belonging to "
                                      "parametricjob is %d.%d: %s",
                                      self.request_id, self.id, dirac_answer['Message'])
                    self.reschedule = False
                else:
                    monitored_jobs = dirac_answer['Value']
                    skipped_jobs = monitor_jobs.difference(monitored_jobs)
                    if skipped_jobs:
                        self.logger.warning("Couldn't check the status of jobs: %s",
                                            list(skipped_jobs))

        statuses = Counter()
        for job in self.dirac_jobs:
            if job.id in rescheduled_jobs:
                job.reschedules += 1
            if job.id in monitored_jobs:
                try:
                    # pylint: disable=unsubscriptable-object
                    job.status = DiracStatus[monitored_jobs[job.id]['Status'].upper()]
                except KeyError:
                    self.logger.warning("Unknown DiracStatus: %s. Setting to UNKNOWN",
                                        monitored_jobs[job.id]['Status'].upper())
                    job.status = DiracStatus.UNKNOWN
            if not isinstance(job.status, DiracStatus):
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

    @classmethod
    def get(cls, request_id=None, parametricjob_id=None, user_id=None):
        """Get parametric jobs."""
        if request_id is not None:
            try:
                request_id = native(int(request_id))
            except ValueError:
                cls.logger.error("Request id: %r should be of type int "
                                 "(or convertable to int)", request_id)
                raise

        if parametricjob_id is not None:
            try:
                parametricjob_id = native(int(parametricjob_id))
            except ValueError:
                cls.logger.error("Parametric job id: %r should be of type int "
                                 "(or convertable to int)", parametricjob_id)
                raise

        if user_id is not None:
            try:
                user_id = native(int(user_id))
            except ValueError:
                cls.logger.error("User id: %r should be of type int "
                                 "(or convertable to int)", user_id)
                raise

        with managed_session() as session:
            query = session.query(cls)
            if request_id is not None:
                query = query.filter_by(request_id=request_id)
            if parametricjob_id is not None:
                query = query.filter_by(id=parametricjob_id)
            if user_id is not None:
                query = query.filter_by(requester_id=user_id)

            if request_id is None or parametricjob_id is None:
                parametricjobs = query.all()
                session.expunge_all()
                parametricjobs.sort(key=attrgetter("id"))
                return parametricjobs

            try:
                parametricjob = query.one()
            except NoResultFound:
                cls.logger.warning("No result found for parametric job id: %d", parametricjob_id)
                raise
            except MultipleResultsFound:
                cls.logger.error("Multiple results found for parametric job id: %d",
                                 parametricjob_id)
                raise
            session.expunge(parametricjob)
            return parametricjob


@event.listens_for(ParametricJobs.status, "set", propagate=True)
def intercept_status_set(target, newvalue, oldvalue, _):
    """Intercept status transitions."""
    # will catch updates in detached state and again when we merge it into session
    if not inspect(target).detached and oldvalue != newvalue:
        target.logger.info("Parametric job %d.%d transitioned from status %s to %s",
                           target.request_id, target.id, oldvalue.name, newvalue.name)


@event.listens_for(SessionRegistry, "persistent_to_deleted")
def intercept_persistent_to_deleted(session, object_):
    """Intercept deletion of object and remove DIRAC jobs."""
    if isinstance(object_, DiracJobs):
        DiracJobs.logger.debug("Local DB Dirac job %d from parametric job %d.%d is being removed.",
                               object_.id, object_.request_id, object_.parametricjob_id)

    if isinstance(object_, ParametricJobs):
        ParametricJobs.logger.info("Parametric job %d.%d is being removed, triggering bulk tidy up "
                                   "of DIRAC job(s).",
                                   object_.request_id, object_.id)
        object_._remove_dirac_jobs()
