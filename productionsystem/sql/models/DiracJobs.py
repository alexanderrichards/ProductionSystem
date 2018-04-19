"""Dirac Jobs Table."""
import logging
import json

import cherrypy
from sqlalchemy import Column, Integer, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from productionsystem.sql.registry import managed_session
from productionsystem.apache_utils import check_credentials, dummy_credentials
from ..enums import DiracStatus
from ..SQLTableBase import SQLTableBase


@cherrypy.expose
@cherrypy.popargs('diracjob_id')
class DiracJobs(SQLTableBase):
    """Dirac Jobs SQL Table."""

    __tablename__ = 'diracjobs'
    id = Column(Integer, primary_key=True)  # pylint: disable=invalid-name
    parametricjob_id = Column(Integer, ForeignKey('parametricjobs.id'), nullable=False)
    status = Column(Enum(DiracStatus), nullable=False, default=DiracStatus.UNKNOWN)
    reschedules = Column(Integer, nullable=False, default=0)
    parametricjob = relationship("ParametricJobs", back_populates='dirac_jobs')
    logger = logging.getLogger(__name__)

    @classmethod
    @cherrypy.tools.accept(media='application/json')
    @cherrypy.tools.json_out()
#    @check_credentials
    @dummy_credentials
    def GET(cls, request_id, parametricjob_id, diracjob_id=None):  # pylint: disable=invalid-name
        """
        REST Get method.

        Returns all DiracJobs for a given request and parametricjob id.
        """
        cls.logger.debug("In GET: reqid = %s, parametricjob_id = %s, diracjob_id", request_id, parametricjob_id, diracjob_id)
        with cherrypy.HTTPError.handle(ValueError, 400, 'Bad request_id: %r' % request_id):
            request_id = int(request_id)
        with cherrypy.HTTPError.handle(ValueError, 400, 'Bad parametricjob_id: %r' % parametricjob_id):
            parametricjob_id = int(parametricjob_id)

        requester = cherrypy.request.verified_user
        with managed_session() as session:
            query = session.query(cls)\
                           .filter_by(parametricjob_id=parametricjob_id)
            if not requester.admin:
                query = not query.join(cls.parametricjob)\
                                 .join(cls.parametricjob.request)\
                                 .filter_by(requester_id=requester.id)
            if diracjob_id is None:
                diracjobs = query.all()
                session.expunge_all()
                return diracjobs

            with cherrypy.HTTPError.handle(ValueError, 400, 'Bad diracjob_id: %r' % diracjob_id):
                diracjob_id = int(diracjob_id)

            try:
                # Does this need to be before the join? will id be requestid or parametricjob id?
                diracjob = query.filter_by(id=diracjob_id).one()
            except NoResultFound:
                message = "No ParametricJobs found with id: %s" % parametricjob_id
                cls.logger.error(message)
                raise cherrypy.NotFound(message)
            except MultipleResultsFound:
                message = "Multiple ParametricJobs found with id: %s" % parametricjob_id
                cls.logger.error(message)
                raise cherrypy.HTTPError(500, message)
            session.expunge(diracjob)
            return diracjob
