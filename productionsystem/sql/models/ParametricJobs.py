"""ParametricJobs Table."""
import os
import json
import logging
from abc import abstractmethod
from datetime import datetime
from collections import defaultdict, Counter
from copy import deepcopy
from tempfile import NamedTemporaryFile

import cherrypy
from sqlalchemy import Column, SmallInteger, Integer, Boolean, TEXT, TIMESTAMP, ForeignKey, Enum, CheckConstraint, event
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from productionsystem.apache_utils import check_credentials, dummy_credentials
from productionsystem.config import getConfig
from productionsystem.monitoring.diracrpc.DiracRPCClient import dirac_api_client, dirac_api_job_client
#from lzproduction.rpc.DiracRPCClient import dirac_api_client, ParametricDiracJobClient
from ..enums import LocalStatus, DiracStatus
from ..registry import managed_session, SessionRegistry
from ..SQLTableBase import SQLTableBase, SmartColumn
from .DiracJobs import DiracJobs


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
                       'polymorphic_identity': 'parametricjobs'}
    id = Column(Integer, primary_key=True)  # pylint: disable=invalid-name
    priority = SmartColumn(SmallInteger, CheckConstraint('priority >= 0 and priority < 10'), nullable=False, default=3, allowed=True)
    site = SmartColumn(TEXT, nullable=False, default='ANY', allowed=True)
    status = Column(Enum(LocalStatus), nullable=False, default=LocalStatus.REQUESTED)
    reschedule = Column(Boolean, nullable=False, default=False)
    timestamp = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    num_jobs = SmartColumn(Integer, nullable=False, required=True)
    num_completed = Column(Integer, nullable=False, default=0)
    num_failed = Column(Integer, nullable=False, default=0)
    num_submitted = Column(Integer, nullable=False, default=0)
    num_running = Column(Integer, nullable=False, default=0)
    request_id = SmartColumn(Integer, ForeignKey('requests.id'), nullable=False, required=True)
    request = relationship("Requests", back_populates="parametric_jobs")
    dirac_jobs = relationship("DiracJobs", back_populates="parametricjob", cascade="all, delete-orphan")
    logger = logging.getLogger(__name__)

    @hybrid_property
    def num_other(self):
        """Return the number of jobs in states other than the known ones."""
        return self.njobs - (self.num_submitted + self.num_running + self.num_failed + self.num_completed)

    def __init__(self, **kwargs):
        required_args = set(self.required_columns).difference(kwargs)
        if required_args:
            raise ValueError("Missing required keyword args: %s" % list(required_args))
        super(ParametricJobs, self).__init__(**subdict(kwargs, self.allowed_columns))

    def update(self):
        with managed_session() as session:
            session.merge(self)

#    @abstractmethod
    def _setup_dirac_job(self, job, tmp_runscript):
        """Setup the DIRAC parametric job."""
        tmp_runscript.write("echo HelloWorld\n")
        tmp_runscript.flush()
        job.setName("Test DIRAC Job")
        job.setExecutable(os.path.basename(tmp_runscript.name))
        return job

    def submit(self):
        """Submit parametric job."""
        with dirac_api_job_client() as (dirac, dirac_job_class), NamedTemporaryFile() as runscript:
            dirac_job = self._setup_dirac_job(dirac_job_class(), runscript)
            result = dirac.submit(dirac_job)
            if not result['OK']:
                self.logger.error("Error submitting dirac job: %s", result['Message'])
                if self.dirac_jobs:
                    jobs = [diracjob.id for diracjob in self.dirac_jobs]
                    self.logger.info("Killing/deleting %d existing dirac jobs.", len(jobs))
                    dirac.kill(jobs)
                    dirac.delete(jobs)
                raise Exception(result['Message'])
            self.dirac_jobs = [DiracJobs(id=i, parametricjob_id=self.id) for i in result['Value']]
            self.logger.info("Successfully submitted %d Dirac jobs for %d.%d",
                             len(self.dirac_jobs), self.request_id, self.id)

    def monitor(self):
        """
        Bulk update status.
        This method updates all DIRAC jobs which belong to the given
        parametricjob.
        """
        # Group jobs by status

        if not self.dirac_jobs:
            self.logger.warning("No dirac jobs associated with parametricjob: %d. returning status unknown", self.id)
            self.status = LocalStatus.UNKNOWN
            self.reschedule = False
            self.num_completed = 0
            self.num_failed = 0
            self.num_submitted = 0
            self.num_running = 0
            return

        job_types = defaultdict(set)
        for job in self.dirac_jobs:
            job_types[job.status].add(job.id)
            # add auto-reschedule jobs
            if job.status in (DiracStatus.FAILED, DiracStatus.STALLED) and job.reschedules < 2:
                job_types['Reschedule'].add(job.id)

        reschedule_jobs = job_types['Reschedule'] if job_types[DiracStatus.DONE] else set()
        monitor_jobs = job_types[DiracStatus.RUNNING] | \
                       job_types[DiracStatus.RECEIVED] | \
                       job_types[DiracStatus.QUEUED] | \
                       job_types[DiracStatus.WAITING] | \
                       job_types[DiracStatus.CHECKING] | \
                       job_types[DiracStatus.MATCHED] | \
                       job_types[DiracStatus.UNKNOWN] | \
                       job_types[DiracStatus.COMPLETED]

        if self.reschedule:
            reschedule_jobs = job_types[DiracStatus.FAILED] | job_types[DiracStatus.STALLED]

        # Reschedule jobs
        rescheduled_jobs = []
        if reschedule_jobs:
            self.logger.info("Rescheduling jobs: %s", list(reschedule_jobs))
            try:
                with dirac_api_client() as dirac:
                    result = deepcopy(dirac.reschedule(reschedule_jobs))
            except Exception as err:
                self.logger.exception("Error calling DIRAC to reschedule jobs: %s", err.message)
            else:
                if not result['OK']:
                    self.logger.error("DIRAC failed to reschedule jobs: %s", result['Message'])
                else:
                    rescheduled_jobs.extend(result['Value'])
                    self.logger.info("Rescheduled jobs: %s", rescheduled_jobs)
                    skipped_jobs = reschedule_jobs.difference(rescheduled_jobs)
                    if skipped_jobs:
                        self.logger.warning("Failed to reschedule jobs: %s", list(skipped_jobs))
                    monitor_jobs.update(rescheduled_jobs)

        # Update status
        monitored_jobs = {}
        self.logger.debug("Monitoring jobs: %s", list(monitor_jobs))
        try:
            with dirac_api_client() as dirac:
                dirac_answer = deepcopy(dirac.status(monitor_jobs))
        except Exception as err:
            self.logger.exception("Error calling DIRAC to monitor jobs: %s", err.message)
        else:
            if not dirac_answer['OK']:
                self.logger.error("DIRAC failed to get statuses for jobs belonging to parametricjob is %d.", self.id)
                self.reschedule = False
            else:
                monitored_jobs = dirac_answer['Value']
                skipped_jobs = monitor_jobs.difference(monitored_jobs)
                if skipped_jobs:
                    self.logger.warning("Couldn't check the status of jobs: %s", list(skipped_jobs))

        statuses = Counter()
        for job in self.dirac_jobs:
            if job.id in rescheduled_jobs:
                job.reschedules += 1
            if job.id in monitored_jobs:
                try:
                    job.status = DiracStatus[monitored_jobs[job.id]['Status'].upper()]
                except KeyError:
                    self.logger.warning("Unknown DiracStatus: %s. Setting to UNKNOWN",
                                        monitored_jobs[job.id]['Status'].upper())
                    job.status = DiracStatus.UNKNOWN
            statuses.update((job.status.local_status,))

        status = max(statuses)
        if status != self.status:
            self.status = status
            self.logger.info("ParametricJob %d moved to state %s", self.id, status.name)

        self.num_completed = statuses[LocalStatus.COMPLETED]
        self.num_failed = statuses[LocalStatus.FAILED]
        self.num_submitted = statuses[LocalStatus.SUBMITTED]
        self.num_running = statuses[LocalStatus.RUNNING]
        self.reschedule = False

    @staticmethod
    def _datatable_format_headers():
        columns = [{'data': 'id', 'title': 'ID', 'className': 'rowid'},
                   {'data': 'status', 'title': 'Status'}]
        cherrypy.response.headers['Datatable-Order'] = json.dumps([[0, 'desc']])
        cherrypy.response.headers["Datatable-Columns"] = json.dumps(columns)

    @classmethod
    def get(cls, parametricjob_id=None, request_id=None, user_id=None):
        """Get parametric jobs."""
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
            query = session.query(cls)
            if parametricjob_id is not None:
                query = query.filter_by(id=parametricjob_id)
            if request_id is not None:
                query = query.filter_by(request_id=request_id)
            if user_id is not None:
                query = query.join(cls.request).filter_by(requester_id=user_id)

            if parametricjob_id is None:
                requests = query.all()
                session.expunge_all()
                return requests

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


@event.listens_for(SessionRegistry, "persistent_to_deleted")
def intercept_persistent_to_deleted(session, object_):
    if isinstance(object_, DiracJobs):
        DiracJobs.logger.debug("Parametric job %d marked for removal, cascade deleting local DB "
                               "Dirac job %d", object_.parametricjob_id, object_.id)

    if isinstance(object_, ParametricJobs):
        ParametricJobs.logger.info("Request %d marked for removal, cascade deleting Parametric "
                                   "job %d triggering bulk tidy up of DIRAC job(s).",
                                   object_.request_id, object_.id)
        dirac_ids = [job.id for job in object_.dirac_jobs]
        try:
            with dirac_api_job_client() as dirac:
                ParametricJobs.logger.info("Killing/deleting %d DIRAC job(s).", len(dirac_ids))
                dirac.kill(dirac_ids)
                dirac.delete(dirac_ids)
        except BaseException:
            ParametricJobs.logger.exception("Error doing DIRAC tidy up. Cleaning up local system "
                                            "and forgetting about the (possibly) orphaned jobs "
                                            "on DIRAC system")
