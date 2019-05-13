"""
Apache Utils.

Tools for dealing with credential checking from X509 SSL certificates.
These are useful when using Apache as a reverse proxy to check user
credentials against a local DB.
"""
# Py2/3 compatibility layer
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *  # pylint: disable=wildcard-import, unused-wildcard-import, redefined-builtin

from functools import wraps
import cherrypy
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
import productionsystem.sql as sql
from productionsystem.sql.models import Users

__all__ = ('apache_client_convert', 'check_credentials', 'admin_only',
           'dummy_credentials', 'DUMMY_USER')


def apache_client_convert(client_dn, client_ca=None):
    """
    Convert Apache style client certs.

    Convert from the Apache comma delimited style to the
    more usual slash delimited style.

    Args:
        client_dn (str): The client DN
        client_ca (str): [Optional] The client CA

    Returns:
        tuple: The converted client (DN, CA)
    """
    if not client_dn.startswith('/'):
        client_dn = '/' + '/'.join(reversed(client_dn.split(',')))
        if client_ca is not None:
            client_ca = '/' + '/'.join(reversed(client_ca.split(',')))
    return client_dn, client_ca


def admin_only(func):
    """Enforce user must be an admin."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not hasattr(cherrypy.request, 'verified_user'):
            raise cherrypy.HTTPError(500,
                                     'User credentials must be checked before enforcing admin_only')
        if not cherrypy.request.verified_user.admin:
            raise cherrypy.HTTPError(403, 'Forbidden: Admin users only')
        return func(*args, **kwargs)
    return wrapper


def check_credentials(func):
    """Check users credentials."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        required_headers = {'Ssl-Client-S-Dn', 'Ssl-Client-I-Dn', 'Ssl-Client-Verify'}
        missing_headers = required_headers.difference(cherrypy.request.headers)
        if missing_headers:
            raise cherrypy.HTTPError(401, 'Unauthorized: Incomplete certificate information '
                                          'available, required: %s' % list(missing_headers))

        client_dn, client_ca = apache_client_convert(cherrypy.request.headers['Ssl-Client-S-Dn'],
                                                     cherrypy.request.headers['Ssl-Client-I-Dn'])
        client_verified = cherrypy.request.headers['Ssl-Client-Verify']
        if client_verified != 'SUCCESS':
            raise cherrypy.HTTPError(401, 'Unauthorized: Cert not verified for user DN: %s, CA: %s.'
                                     % (client_dn, client_ca))

        with sql.managed_session() as session:
            try:
                user = session.query(sql.models.Users) \
                    .filter_by(dn=client_dn, ca=client_ca) \
                    .one()
            except MultipleResultsFound:
                raise cherrypy.HTTPError(500, 'Internal Server Error: Duplicate user detected. '
                                              'user: (%s, %s)'
                                         % (client_dn, client_ca))
            except NoResultFound:
                raise cherrypy.HTTPError(403, 'Forbidden: Unknown user. user: (%s, %s)'
                                         % (client_dn, client_ca))
            except Exception as err:
                raise cherrypy.HTTPError(500,
                                         "Internal Server Error: Unknown Exception caught %s-> %s"
                                         % (type(err), err.message))
            if user.suspended:
                raise cherrypy.HTTPError(403, 'Forbidden: User is suspended by VO. user: (%s, %s)'
                                         % (client_dn, client_ca))
            session.expunge(user)
            cherrypy.request.verified_user = user
        return func(*args, **kwargs)
    return wrapper


DUMMY_USER = Users(id=17, dn='/test/CN=dummy user/testdn', ca='ca', email='test@email.com',
                   suspended=False, admin=True)


def dummy_credentials(func):
    """Assign dummy credentials for testing."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        cherrypy.request.verified_user = DUMMY_USER
        return func(*args, **kwargs)
    return wrapper
