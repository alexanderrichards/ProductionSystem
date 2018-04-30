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
from ..SQLTableBase import SQLTableBase, SmartColumn
from ..models import ParametricJobs
from .Users import Users
#from .ParametricJobs import ParametricJobs


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
                       'polymorphic_identity': 'requests'}
    id = Column(Integer, primary_key=True)  # pylint: disable=invalid-name
    description = SmartColumn(TEXT, nullable=True, allowed=True)
    requester_id = SmartColumn(Integer, ForeignKey('users.id'), nullable=False, required=True)
    request_date = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    status = Column(Enum(LocalStatus), nullable=False, default=LocalStatus.REQUESTED)
    timestamp = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    parametric_jobs = relationship("ParametricJobs", back_populates="request", cascade="all, delete-orphan")
    logger = logging.getLogger(__name__)

    def __init__(self, **kwargs):
        required_args = set(self.required_columns).difference(kwargs)
        if required_args:
            raise ValueError("Missing required keyword args: %s" % list(required_args))
        super(Requests, self).__init__(**subdict(kwargs, self.allowed_columns))
        
    def submit(self):
        """Submit Request."""
        self.logger.info("Submitting request %s", self.id)
        try:
            for job in self.parametric_jobs:
                job.submit()
        except:
            self.logger.exception("Exception while submitting request %s", self.id)
            raise

    def update_status(self):
        """Update request status."""
        if not self.parametric_jobs:
            self.logger.warning("No parametric jobs associated with request: %d. returning status unknown", self.id)
            self.status = LocalStatus.UNKNOWN
            return

        statuses = []
        for job in self.parametric_jobs:
            try:
                job.update_status()
            except:
                self.logger.exception("Exception updating ParametricJob %s", job.id)
            statuses.append(job.status)

        status = max(statuses)
        if status != self.status:
            self.status = status
            self.logger.info("Request %d moved to state %s", self.id, status.name)

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
    @cherrypy.tools.json_out()
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
                return [dict(request.jsonable(),
                             requester=user.name)
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
            return dict(request.jsonable(),
                        requester=user.name)

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
#    @check_credentials
#    @admin_only
    @dummy_credentials
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
#    @check_credentials
    @dummy_credentials
    def POST(cls):  # pylint: disable=invalid-name
        """REST Post method."""
        data = cherrypy.request.json
        cls.logger.debug("In POST: kwargs = %s", data)
        if not isinstance(data, dict):
            message = "Request data is expected to be JSON object."
            cls.logger.error(message)
            raise cherrypy.HTTPError(400, message)
        if 'request' not in data:
            message = "Request data should contain 'request' as a subobject."
            cls.logger.error(message)
            raise cherrypy.HTTPError(400, message)
        data['request'].pop('requester_id', None)
        try:
            request = cls(requester_id=cherrypy.request.verified_user.id, **data["request"])
        except ValueError:
            message = "Error creating request, bad input."
            cls.logger.exception(message)
            raise cherrypy.HTTPError(400, message)

        parametricjobs = data.get("parametricjobs", [])
        if not parametricjobs:
            cls.logger.warning("No parametric jobs requested.")
        request.parametric_jobs = []
        for job in parametricjobs:
            try:
                request.parametric_jobs.append(ParametricJobs(**job))
            except ValueError:
                message = "Error creating parametricjob, bad input."
                cls.logger.exception(message)
                raise cherrypy.HTTPError(400, message)
        with managed_session() as session:
            session.add(request)
            session.flush()
            session.refresh(request)
            cls.logger.info("New Request %d added", request.id)


# Have to add this after class is defined as ParametricJobs SQL setup requires it to be defined.
Requests.parametricjobs = ParametricJobs()
