"""Requests Table."""
# Py2/3 compatibility layer
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *  # pylint: disable=wildcard-import, unused-wildcard-import, redefined-builtin

import json
import logging
from datetime import datetime
from operator import attrgetter

from future.utils import native
import cherrypy
from sqlalchemy import Column, Integer, TIMESTAMP, TEXT, ForeignKey, Enum, event, inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import relationship, joinedload
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from ..enums import LocalStatus
from ..registry import managed_session
from ..SQLTableBase import SQLTableBase, SmartColumn
from ..models import ParametricJobs
from .Users import Users
# from .ParametricJobs import ParametricJobs


def subdict(dct, keys, **kwargs):
    """Create a sub dictionary."""
    out = {k: dct[k] for k in keys if k in dct}
    out.update(kwargs)
    return out


@cherrypy.expose
@cherrypy.popargs('request_id')
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
    request_date = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    status = Column(Enum(LocalStatus), nullable=False, default=LocalStatus.REQUESTED)
    timestamp = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    parametric_jobs = relationship("ParametricJobs", cascade="all, delete-orphan")
    requester = relationship("Users")
    logger = logging.getLogger(__name__)

    def __init__(self, **kwargs):
        """Initialise."""
        required_args = set(self.required_columns).difference(kwargs)  # pylint: disable=no-member
        if required_args:
            raise ValueError("Missing required keyword args: %s" % list(required_args))
        # pylint: disable=no-member
        super(Requests, self).__init__(**subdict(kwargs, self.allowed_columns))
        parametricjobs = kwargs.get('parametricjobs', [])
        if not parametricjobs:
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
                self.logger.exception("Error creating parametricjob, bad input: %s", parametricjob)
                raise

    def add(self):
        """Add self to the DB."""
        with managed_session() as session:
            session.add(self)
            session.flush()
            session.refresh(self)
            session.expunge(self)

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
        self.logger.info("Submitting request %s", self.id)
        try:
            for job in self.parametric_jobs:
                job.submit()
        except BaseException:
            self.logger.exception("Unhandled exception while submitting request %s", self.id)
            self.status = LocalStatus.FAILED

    def monitor(self):
        """Update request status."""
        self.logger.info("Monitoring request %s", self.id)
        if not self.parametric_jobs:
            self.logger.warning("No parametric jobs associated with request: %d. "
                                "returning status unknown", self.id)
            self.status = LocalStatus.UNKNOWN
            return

        status = LocalStatus.UNKNOWN
        for job in self.parametric_jobs:
            try:
                job.monitor()
            # get rid of this if parametricjob catches everything. Only when sure as it's complex
            except BaseException:
                self.logger.exception("Unhandled exception monitoring ParametricJob %s", job.id)
                job.status = LocalStatus.UNKNOWN
            status = max(status, job.status)

        if status != self.status:
            self.status = status

    @classmethod
    def delete(cls, request_id):
        """Delete a requests from the DB."""
        try:
            request_id = native(int(request_id))
        except ValueError:
            cls.logger.error("Request id: %r should be of type int "
                             "(or convertable to int)", request_id)
            raise

        with managed_session() as session:
            try:
                request = session.query(cls).filter_by(id=request_id).one()
            except NoResultFound:
                cls.logger.warning("No result found for request id: %d", request_id)
                raise
            except MultipleResultsFound:
                cls.logger.error("Multiple results found for request id: %d", request_id)
                raise
            session.delete(request)
            cls.logger.info("Request %d deleted.", request_id)

    @classmethod
    def get(cls, request_id=None, user_id=None,
            load_user=False, load_parametricjobs=False, status=None):
        """Get requests."""
        if request_id is not None:
            try:
                if isinstance(request_id, (list, tuple)):
                    request_id = [native(int(i)) for i in request_id]
                else:
                    request_id = native(int(request_id))
            except ValueError:
                cls.logger.error("Request id: %r should be of type int "
                                 "(or convertable to int)", request_id)
                raise

        if user_id is not None:
            try:
                user_id = native(int(user_id))
            except ValueError:
                cls.logger.error("User id: %r should be of type int "
                                 "(or convertable to int)", user_id)
                raise

        if status is not None:
            if not isinstance(status, (list, tuple)):
                cls.logger.error("Status: %r should be of type list/tuple", status)
                raise TypeError

        with managed_session() as session:
            query = session.query(cls)
            if load_user:
                query = query.options(joinedload(cls.requester, innerjoin=True))
            if load_parametricjobs:
                query = query.options(joinedload(cls.parametric_jobs)
                                      .joinedload(ParametricJobs.dirac_jobs))
            if user_id is not None:
                query = query.filter_by(requester_id=user_id)
            if status is not None:
                query = query.filter(cls.status.in_(status))

            if request_id is None:
                requests = query.all()
                session.expunge_all()
                requests.sort(key=attrgetter('id'))
                return requests

            if isinstance(request_id, (list, tuple)):
                requests = query.filter(cls.id.in_(request_id)).all()
                session.expunge_all()
                requests.sort(key=attrgetter('id'))
                return requests

            try:
                request = query.filter_by(id=request_id).one()
            except NoResultFound:
                cls.logger.warning("No result found for request id: %d", request_id)
                raise
            except MultipleResultsFound:
                cls.logger.error("Multiple results found for request id: %d", request_id)
                raise
            # Need the all if loading the user db object as well.
            # If not then doesn't hurt as only one object this session
            session.expunge_all()
            return request

    @classmethod
    def get_reschedules(cls):
        """Get Requests with ParametricJobs to reschedule."""
        with managed_session() as session:
            requests = session.query(cls)\
                              .options(joinedload(cls.parametric_jobs)
                                       .joinedload(ParametricJobs.dirac_jobs))\
                              .filter_by(status=LocalStatus.FAILED)\
                              .join(cls.parametric_jobs)\
                              .filter_by(reschedule=True)\
                              .all()
            session.expunge_all()
            return requests


@event.listens_for(Requests.status, "set", propagate=True)
def intercept_status_set(target, newvalue, oldvalue, _):
    """Intercept status transitions."""
    # will catch updates in detached state and again when we merge it into session
    if not inspect(target).detached and oldvalue != newvalue:
        target.logger.info("Request %d transitioned from status %s to %s",
                           target.id, oldvalue.name, newvalue.name)
