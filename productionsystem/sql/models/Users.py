"""Users Table."""
# Py2/3 compatibility layer
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *  # pylint: disable=wildcard-import, unused-wildcard-import, redefined-builtin

import logging
import cherrypy
from distutils.util import strtobool  # pylint: disable=import-error, no-name-in-module
from sqlalchemy import Column, Integer, TEXT, Boolean
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from ..registry import managed_session
from ..SQLTableBase import SQLTableBase


@cherrypy.expose
@cherrypy.popargs('user_id')
class Users(SQLTableBase):
    """Users SQL Table."""

    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)  # pylint: disable=invalid-name
    dn = Column(TEXT, nullable=False)  # pylint: disable=invalid-name
    ca = Column(TEXT, nullable=False)  # pylint: disable=invalid-name
    email = Column(TEXT, nullable=False)
    suspended = Column(Boolean, nullable=False)
    admin = Column(Boolean, nullable=False)
    logger = logging.getLogger(__name__)

    @property
    def name(self):
        """
        Human-readable name from DN.

        Attempt to determine a meaningful name from a
        clients DN. Requires the DN to have already been
        converted to the more usual slash delimeted style.
        If multiple CN fields exist in the DN then the longest
        is assumend to be the desired human readable field.

        Returns:
            str: The human-readable name
        """
        cns = (token[len('CN='):] for token in self.dn.split('/')
               if token.startswith('CN='))
        return sorted(cns, key=len)[-1]

    def __hash__(self):
        """hash."""
        return hash((self.dn, self.ca))

    def __eq__(self, other):
        """equality check."""
        return (self.dn, self.ca) == (other.dn, other.ca)

    def update(self):
        """Update the DB record from this Users object."""
        with managed_session() as session:
            session.merge(self)

    @classmethod
    def get_users(cls, user_id=None):
        """
        Get users from database.

        Gets all users in database or explicitly those with a given user_id.

        Args:
            user_id (int): User id to extract

        Returns:
            list/Users: The users/user pulled from the database
        """
        if user_id is not None:
            try:
                user_id = int(user_id)
            except ValueError:
                cls.logger.error("User id: %r should be of type int "
                                 "(or convertable to int)", user_id)
                raise

        with managed_session() as session:
            query = session.query(cls)
            if user_id is None:
                users = query.all()
                session.expunge_all()
                return users

            try:
                user = query.filter_by(id=user_id).one()
            except NoResultFound:
                cls.logger.warning("No result found for user id: %d", user_id)
                raise
            except MultipleResultsFound:
                cls.logger.error("Multiple results found for user id: %d", user_id)
                raise
            session.expunge(user)
            return user
'''
    @classmethod
    @cherrypy.tools.accept(media='application/json')
    @cherrypy.tools.json_out()
    @dummy_credentials
#    @check_credentials
#    @admin_only
    def GET(cls, user_id=None):
        """REST GET method."""
        cls.logger.debug("In GET: user_id = %r", user_id)
        with managed_session() as session:
            query = session.query(cls)
            if user_id is None:
                users = query.all()
                session.expunge_all()
                return users

            with cherrypy.HTTPError.handle(ValueError, 400, 'Bad user_id: %r' % user_id):
                user_id = int(user_id)

            try:
                user = query.filter_by(id=user_id).one()
            except NoResultFound:
                message = 'No matching user found.'
                cls.logger.warning(message)
                raise cherrypy.NotFound(message)
            except MultipleResultsFound:
                message = 'Multiple matching users found.'
                cls.logger.error(message)
                raise cherrypy.HTTPError(500, message)
            session.expunge(user)
            return user

    @classmethod
    @check_credentials
    @admin_only
    def PUT(cls, user_id, admin):  # pylint: disable=invalid-name
        """REST Put method."""
        cls.logger.debug("In PUT: user_id = %s, admin = %s", user_id, admin)
        with cherrypy.HTTPError.handle(ValueError, 400, 'Bad user_id: %r' % user_id):
            user_id = int(user_id)
        with cherrypy.HTTPError.handle(ValueError, 400, 'Bad admin value'):
            admin = bool(strtobool(admin))

        with managed_session() as session:
            try:
                user = session.query(cls).filter_by(id=user_id).one()
            except NoResultFound:
                message = "No matching user found."
                cls.logger.warning(message)
                raise cherrypy.NotFound(message)
            except MultipleResultsFound:
                message = "Multiple matching users found."
                cls.logger.error(message)
                raise cherrypy.HTTPError(500, message)
            user.admin = admin
'''
