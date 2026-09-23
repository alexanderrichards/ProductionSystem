"""
Apache Utils.

Tools for dealing with credential checking from X509 SSL certificates.
These are useful when using Apache as a reverse proxy to check user
credentials against a local DB.
"""
from __future__ import annotations
from typing import TYPE_CHECKING
from fastapi import Depends, Form, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound, MultipleResultsFound
import productionsystem.sql as sql
from productionsystem.sql.enums import LocalStatus
if TYPE_CHECKING:
    from productionsystem.sql.models.Users import Users, User
else:
    from productionsystem.sql.models import Users

__all__ = ('apache_client_convert', 'get_requested_status', 'get_verified_user', 'admin_only',
           'get_dummy_user', 'DUMMY_USER')


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


def get_requested_status(status: str = Form(...)) -> LocalStatus:
    """
    FastAPI dependency: parse the requested status from the form data.
    
    This would usually be in the form of a string like "APPROVED" or "RUNNING" so
    convert to a LocalStatus enum member. Since LocalStatus is an IntEnum, the default FastAPI
    conversion would only work if the client passed an integer value corresponding to the enum member
    e.g. 1 for LocalStatus.APPROVED. This is not as user friendly as passing a string like "APPROVED" directly.
    """
    try:
        return LocalStatus[status.upper()]
    except KeyError as err:
        raise HTTPException(400, f"Invalid status: {status!r}") from err


def get_verified_user(request: Request) -> User:
    """FastAPI dependency: verify the client's certificate headers and return the DB user."""
    required_headers = {'Ssl-Client-S-Dn', 'Ssl-Client-I-Dn', 'Ssl-Client-Verify'}
    missing_headers = required_headers.difference(request.headers)
    if missing_headers:
        raise HTTPException(401, 'Unauthorized: Incomplete certificate information '
                                 'available, required: %s' % list(missing_headers))

    client_dn, client_ca = apache_client_convert(request.headers['Ssl-Client-S-Dn'],
                                                 request.headers['Ssl-Client-I-Dn'])
    client_verified = request.headers['Ssl-Client-Verify']
    if client_verified != 'SUCCESS':
        raise HTTPException(401, 'Unauthorized: Cert not verified for user DN: %s, CA: %s.'
                                 % (client_dn, client_ca))

    with sql.managed_session() as session:
        try:
            user = session.scalars(
                select(Users)
                .where(Users.dn == client_dn)
                .where(Users.ca == client_ca)  # can use a single where with two args instead
            ).one()
        except MultipleResultsFound as err:
            raise HTTPException(500, 'Internal Server Error: Duplicate user detected. user: (%s, %s)'
                                     % (client_dn, client_ca)) from err
        except NoResultFound as err:
            raise HTTPException(403, 'Forbidden: Unknown user. user: (%s, %s)'
                                     % (client_dn, client_ca)) from err
        except Exception as err:
            raise HTTPException(500,
                                "Internal Server Error: Unknown Exception caught %s-> %s"
                                % (type(err), err)) from err
        if user.suspended:
            raise HTTPException(403, 'Forbidden: User is suspended by VO. user: (%s, %s)'
                                     % (client_dn, client_ca))
    return User.model_validate(user)


def admin_only(user: User = Depends(get_verified_user)) -> User:
    """FastAPI dependency: enforce that the verified user is an admin."""
    if not user.admin:
        raise HTTPException(403, 'Forbidden: Admin users only')
    return user


DUMMY_USER = Users(id=17, dn='/test/CN=dummy user/testdn', ca='ca', email='test@email.com',
                   suspended=False, admin=True)


def get_dummy_user() -> User:
    """Dependency override providing dummy credentials for testing/mock mode."""
    return User.model_validate(DUMMY_USER)
