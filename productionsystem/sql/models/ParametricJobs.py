"""ParametricJobs Table."""
import os
import re
import time
import json
import logging
import calendar
from datetime import datetime

import cherrypy
from sqlalchemy import Column, SmallInteger, Integer, Boolean, TEXT, TIMESTAMP, ForeignKey, Enum, CheckConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from productionsystem.apache_utils import check_credentials
#from lzproduction.rpc.DiracRPCClient import dirac_api_client, ParametricDiracJobClient
from ..utils import db_session
from ..enums import LocalStatus
from ..registry import managed_session
from .SQLTableBase import SQLTableBase
from ..JSONTableEncoder import JSONTableEncoder
#from .DiracJobs import DiracJobs


def json_handler(*args, **kwargs):
    """Handle JSON encoding of response."""
    value = cherrypy.serving.request._json_inner_handler(*args, **kwargs)
    return json.dumps(value, cls=JSONTableEncoder)


@cherrypy.expose
@cherrypy.popargs('parametricjob_id')
class ParametricJobs(SQLTableBase):
    """Jobs SQL Table."""

    __tablename__ = 'parametricjobs'
    logger = logging.getLogger(__name__)  # pylint: disable=invalid-name
    id = Column(Integer, primary_key=True)  # pylint: disable=invalid-name
    priority = Column(SmallInteger, CheckConstraint('priority >= 0 and priority < 10'), nullable=False, default=3)
    site = Column(TEXT, nullable=False, default='ANY')
    status = Column(Enum(LocalStatus), nullable=False)
    reschedule = Column(Boolean, nullable=False, default=False)
    timestamp = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    num_jobs = Column(Integer, nullable=False)
    num_completed = Column(Integer, nullable=False, default=0)
    num_failed = Column(Integer, nullable=False, default=0)
    num_submitted = Column(Integer, nullable=False, default=0)
    num_running = Column(Integer, nullable=False, default=0)
    request_id = Column(Integer, ForeignKey('requests.id'), nullable=False)
    request = relationship("Requests", back_populates="parametric_jobs")
#    diracjobs = relationship("DiracJobs", back_populates="parametricjob")

    @hybrid_property
    def num_other(self):
        """Return the number of jobs in states other than the known ones."""
        return self.njobs - (self.num_submitted + self.num_running + self.num_failed + self.num_completed)

    def submit(self):
        """Submit parametric job."""
        with db_session() as session:
            session.bulk_insert_mappings(DiracJobs, [{'id': i, 'parametricjob_id': self.id}
                                                     for i in dirac_ids])

    def reset(self):
        """Reset parametric job."""
        with db_session(reraise=False) as session:
            dirac_jobs = session.query(DiracJobs).filter_by(parametricjob_id=self.id)
            dirac_job_ids = [j.id for j in dirac_jobs.all()]
            dirac_jobs.delete(synchronize_session=False)
        with dirac_api_client() as dirac:
            logger.info("Removing Dirac jobs %s from ParametricJob %s", dirac_job_ids, self.id)
            dirac.kill(dirac_job_ids)
            dirac.delete(dirac_job_ids)

    def update_status(self):
        """Update the status of parametric job."""
        local_statuses = DiracJobs.update_status(self)
        # could just have DiracJobs return this... maybe better
#        local_statuses = Counter(status.local_status for status in dirac_statuses.elements())
        status = max(local_statuses or [self.status])
        with db_session() as session:
            this = session.merge(self)
            this.status = status
            this.num_completed = local_statuses[LOCALSTATUS.Completed]
            this.num_failed = local_statuses[LOCALSTATUS.Failed]
            this.num_submitted = local_statuses[LOCALSTATUS.Submitted]
            this.num_running = local_statuses[LOCALSTATUS.Running]
            this.reschedule = False
        return status


    @classmethod
    @cherrypy.tools.accept(media='application/json')
    @cherrypy.tools.json_out(handler=json_handler)
    @check_credentials
    def GET(cls, request_id, parametricjob_id=None):  # pylint: disable=invalid-name
        """
        REST Get method.

        Returns all ParametricJobs for a given request id.
        """
        cls.logger.debug("In GET: reqid = %s, parametricjob_id = %s", request_id, parametricjob_id)
        requester = cherrypy.request.verified_user
        with managed_session() as session:
            query = session.query(cls)\
                           .filter_by(request_id=request_id)
            if parametricjob_id is not None:
                query = query.filter_by(id=parametricjob_id)
            if not requester.admin:
                query = query.join(cls.request)\
                             .filter_by(requester_id=requester.id)
            return query.all()

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
