"""Requests Table."""
import json
import logging
from datetime import datetime

import cherrypy
from sqlalchemy import Column, Integer, TIMESTAMP, TEXT, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from productionsystem.apache_utils import check_credentials, admin_only, dummy_credentials
from ..enums import LocalStatus
from ..registry import managed_session
from ..JSONTableEncoder import JSONTableEncoder
from ..SQLTableBase import SQLTableBase
from .Users import Users
from .ParametricJobs import ParametricJobs


def json_handler(*args, **kwargs):
    """Handle JSON encoding of response."""
    value = cherrypy.serving.request._json_inner_handler(*args, **kwargs)
    return json.dumps(value, cls=JSONTableEncoder)


def subdict(dct, keys):
    """Create a sub dictionary."""
    return {k: dct[k] for k in keys if k in dct}


@cherrypy.expose
@cherrypy.popargs('request_id')
class Requests(SQLTableBase):
    """Requests SQL Table."""

    __tablename__ = 'requests'
    id = Column(Integer, primary_key=True)  # pylint: disable=invalid-name
    description = Column(TEXT, nullable=True)
    requester_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    request_date = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    status = Column(Enum(LocalStatus), nullable=False, default=LocalStatus.REQUESTED)
    timestamp = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    parametric_jobs = relationship("ParametricJobs", back_populates="request", cascade="all, delete-orphan")
    logger = logging.getLogger(__name__)

    def submit(self):
        """Submit Request."""
        with db_session() as session:
            parametricjobs = session.query(ParametricJobs).filter_by(request_id=self.id).all()
            session.expunge_all()
            session.merge(self).status = LocalStatus.SUBMITTING

        self.logger.info("Submitting request %s", self.id)

        submitted_jobs = []
        try:
            for job in parametricjobs:
                job.submit()
                submitted_jobs.append(job)
        except:
            self.logger.exception("Exception while submitting request %s", self.id)
            self.logger.info("Resetting associated ParametricJobs")
            for job in submitted_jobs:
                job.reset()


    def update_status(self):
        """Update request status."""
        with db_session() as session:
            parametricjobs = session.query(ParametricJobs).filter_by(request_id=self.id).all()
            session.expunge_all()

        statuses = []
        for job in parametricjobs:
            try:
                statuses.append(job.update_status())
            except:
                self.logger.exception("Exception updating ParametricJob %s", job.id)

        status = max(statuses or [self.status])
        if status != self.status:
            with db_session(reraise=False) as session:
                session.merge(self).status = status
            self.logger.info("Request %s moved to state %s", self.id, status.name)

    @staticmethod
    def _datatable_format_headers():
        columns = [{"data": "id", "title": "ID", "className": "rowid", "width": "5%"},
                   {"data": "description", "title": "Description", "width": "80%"},
                   {"data": "status", "title": "Status", "width": "7.5%"},
                   {"data": "request_date", "title": "Request Date", "width": "7.5%"}]
        if cherrypy.request.verified_user.admin:
            columns[2]['width'] = "70%"
            columns.append({"data": "requester", "title": "Requester", "width": "10%"})

        cherrypy.response.headers['Datatable-Order'] = json.dumps([[1, "desc"]])
        cherrypy.response.headers["Datatable-Columns"] = json.dumps(columns)

    @classmethod
    @cherrypy.tools.accept(media='application/json')
    @cherrypy.tools.json_out(handler=json_handler)
    @dummy_credentials
#    @check_credentials
    def GET(cls, request_id=None):  # pylint: disable=invalid-name
        """REST Get method."""
        cls.logger.debug("In GET: reqid = %r", request_id)
        requester = cherrypy.request.verified_user

        if request_id is not None:
            with cherrypy.HTTPError.handle(ValueError, 400, 'Bad request_id: %r' % request_id):
                request_id = int(request_id)

        with managed_session() as session:
            if not requester.admin:
                query = session.query(cls).filter_by(requester_id=requester.id)
                if request_id is None:
                    cls._datatable_format_headers()
                    requests = query.all()
                    session.expunge_all()
                    return requests
                try:
                    request = query.filter_by(id=request_id).one()
                except NoResultFound:
                    message = "No Request found with id: %s" % request_id
                    cls.logger.warning(message)
                    raise cherrypy.NotFound(message)
                except MultipleResultsFound:
                    message = "Multiple Requests found with id: %s!" % request_id
                    cls.logger.error(message)
                    raise cherrypy.HTTPError(500, message)
                session.expunge(request)
                return request

            query = session.query(cls, Users)
            if request_id is None:
                cls._datatable_format_headers()
                return [dict(request,
                             requester=user.name,
                             status=request.status.name.capitalize())
                        for request, user in query.join(Users, cls.requester_id == Users.id).all()]
            try:
                request, user = query.filter_by(id=request_id)\
                                     .join(Users, cls.requester_id == Users.id)\
                                     .one()
            except NoResultFound:
                message = "No Request found with id: %s" % request_id
                cls.logger.warning(message)
                raise cherrypy.NotFound(message)
            except MultipleResultsFound:
                message = "Multiple Requests found with id: %s!" % request_id
                cls.logger.error(message)
                raise cherrypy.HTTPError(500, message)
            return dict(request,
                        requester=user.name,
                        status=request.status.name.capitalize())

    @classmethod
    @check_credentials
    @admin_only
    def DELETE(cls, request_id):  # pylint: disable=invalid-name
        """REST Delete method."""
        cls.logger.info("Deleting Request id: %s", request_id)
#        if not cherrypy.request.verified_user.admin:
#            raise cherrypy.HTTPError(401, "Unauthorised")
        with cherrypy.HTTPError.handle(ValueError, 400, 'Bad request_id: %r' % request_id):
            request_id = int(request_id)
        with managed_session() as session:
            try:
                #  request = session.query(Requests).filter_by(id=request_id).delete()
                request = session.query(cls).filter_by(id=request_id).one()
            except NoResultFound:
                message = "No Request found with id: %s" % request_id
                cls.logger.warning(message)
                raise cherrypy.NotFound(message)
            except MultipleResultsFound:
                message = "Multiple Requests found with id: %s!" % request_id
                cls.logger.error(message)
                raise cherrypy.HTTPError(500, message)

            session.delete(request)
            cls.logger.info("Request %d deleted.", request_id)

    @classmethod
    @check_credentials
    @admin_only
    def PUT(cls, request_id, status):  # pylint: disable=invalid-name
        """REST Put method."""
        cls.logger.debug("In PUT: reqid = %s, status = %s", request_id, status)
#        if not cherrypy.request.verified_user.admin:
#            raise cherrypy.HTTPError(401, "Unauthorised")
        with cherrypy.HTTPError.handle(ValueError, 400, 'Bad request_id: %r' % request_id):
            request_id = int(request_id)
        if status.upper() not in LocalStatus.members_names():
            raise cherrypy.HTTPError(400, "bad status")

        with managed_session() as session:
            try:
                request = session.query(cls).filter_by(id=request_id).one()
            except NoResultFound:
                message = "No Request found with id: %s" % request_id
                cls.logger.warning(message)
                raise cherrypy.NotFound(message)
            except MultipleResultsFound:
                message = "Multiple Requests found with id: %s!" % request_id
                cls.logger.error(message)
                raise cherrypy.HTTPError(500, message)

            request.status = LocalStatus[status.upper()]
            cls.logger.info("Request %d changed to status %s", request_id, status.upper())

    @classmethod
    @cherrypy.tools.json_in()
    @check_credentials
    def POST(cls):  # pylint: disable=invalid-name
        """REST Post method."""
        data = cherrypy.request.json
        cls.logger.debug("In POST: kwargs = %s", data)

        request = cls(requester_id=cherrypy.request.verified_user.id)
        request.parametric_jobs = []
        for job in data:
            request.parametric_jobs.append(ParametricJobs(**subdict(job,
                                                                    ('allowed'))))
        with managed_session() as session:
            session.add(request)
            cls.logger.info("New Request %d added", request.id)

# Have to add this after class is defined as ParametricJobs SQL setup requires it to be defined.
Requests.parametricjobs = ParametricJobs()
