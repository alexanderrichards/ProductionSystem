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
from ..registry import managed_session
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

    def update_status(self):
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
        if reschedule_jobs:
            self.logger.info("Rescheduling jobs: %s", list(reschedule_jobs))
            with dirac_api_client() as dirac:
                result = deepcopy(dirac.reschedule(reschedule_jobs))
            if result['OK']:
                self.logger.info("Rescheduled jobs: %s", result['Value'])
                skipped_jobs = reschedule_jobs.difference(result["Value"])
                if skipped_jobs:
                    self.logger.warning("Failed to reschedule jobs: %s", list(skipped_jobs))
                monitor_jobs.update(result['Value'])
                reschedule_jobs = set(result['Value'])
            else:
                self.logger.error("Problem rescheduling jobs: %s", result['Message'])

        # Update status
        with dirac_api_client() as dirac:
            dirac_answer = deepcopy(dirac.status(monitor_jobs))
        if not dirac_answer['OK']:
            self.logger.error("Problem getting monitored job statuses from DIRAC for parametricjob is %d.", self.id)
            self.reschedule = False
            return
        dirac_statuses = dirac_answer['Value']

        skipped_jobs = monitor_jobs.difference(dirac_statuses)
        if skipped_jobs:
            self.logger.warning("Couldn't check the status of jobs: %s", list(skipped_jobs))

        statuses = Counter()
        for job in self.dirac_jobs:
            if job.id in reschedule_jobs:
                job.reschedules += 1
            if job.id in dirac_statuses:
                job.status = DiracStatus[dirac_statuses[job.id]['Status'].upper()]
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
    @cherrypy.tools.accept(media='application/json')
    @cherrypy.tools.json_out()
#    @check_credentials
    @dummy_credentials
    def GET(cls, request_id, parametricjob_id=None):  # pylint: disable=invalid-name
        """
        REST Get method.

        Returns all ParametricJobs for a given request id.
        """
        cls.logger.debug("In GET: reqid = %s, parametricjob_id = %s", request_id, parametricjob_id)
        with cherrypy.HTTPError.handle(ValueError, 400, 'Bad request_id: %r' % request_id):
            request_id = int(request_id)

        requester = cherrypy.request.verified_user
        with managed_session() as session:
            query = session.query(cls)\
                           .filter_by(request_id=request_id)
            if not requester.admin:
                query = query.join(cls.request)\
                             .filter_by(requester_id=requester.id)
            if parametricjob_id is None:
                cls._datatable_format_headers()
                parametricjobs = query.all()
                session.expunge_all()
                return parametricjobs

            with cherrypy.HTTPError.handle(ValueError, 400, 'Bad parametricjob_id: %r' % parametricjob_id):
                parametricjob_id = int(parametricjob_id)

            try:
                # Does this need to be before the join? will id be requestid or parametricjob id?
                parametricjob = query.filter_by(id=parametricjob_id).one()
            except NoResultFound:
                message = "No ParametricJobs found with id: %s" % parametricjob_id
                cls.logger.error(message)
                raise cherrypy.NotFound(message)
            except MultipleResultsFound:
                message = "Multiple ParametricJobs found with id: %s" % parametricjob_id
                cls.logger.error(message)
                raise cherrypy.HTTPError(500, message)
            session.expunge(parametricjob)
            return parametricjob

    @classmethod
    @check_credentials
    def PUT(cls, request_id, parametricjob_id, reschedule=False):  # pylint: disable=invalid-name
        """REST Put method."""
        cls.logger.debug("In PUT: request_id = %s, jobid = %s, reschedule = %s",
                         request_id, parametricjob_id, reschedule)
        requester = cherrypy.request.verified_user
        with managed_session() as session:
            query = session.query(cls).filter_by(id=parametricjob_id)
            if not requester.admin:
                query = query.join(cls.request)\
                             .filter_by(requester_id=requester.id)
            try:
                job = query.one()
            except NoResultFound:
                message = "No ParametricJobs found with id: %s" % parametricjob_id
                cls.logger.error(message)
                raise cherrypy.NotFound(message)
            except MultipleResultsFound:
                message = "Multiple ParametricJobs found with id: %s" % parametricjob_id
                cls.logger.error(message)
                raise cherrypy.HTTPError(500, message)
            if reschedule and not job.reschedule:
                job.reschedule = True
                job.status = LocalStatus.SUBMITTING


#ParametricJobs.diracjobs = DiracJobs()
@event.listens_for(ParametricJobs, 'before_delete')
def receive_before_delete(mapper, connection, target):
    "listen for the 'before_delete' event"
    pass
