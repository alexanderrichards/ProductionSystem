"""
Apache Utils.

Tools for dealing with credential checking from X509 SSL certificates.
These are useful when using Apache as a reverse proxy to check user
credentials against a local DB.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Form, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import MultipleResultsFound, NoResultFound

import productionsystem.sql as sql
from productionsystem.sql.enums import LocalStatus
from productionsystem.sql.models import User, Users

__all__ = ('get_requested_status', 'get_verified_user', 'admin_only',
           'get_dummy_user', 'DUMMY_USER', 'VerifiedUser', 'RequestedStatus', 'AdminUser')


def _apache_client_convert(client_dn, client_ca=None):
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

    Returns:
        LocalStatus: Status enum member named by the submitted form value.
    """
    try:
        return LocalStatus[status.upper()]
    except KeyError as err:
        raise HTTPException(400, f"Invalid status: {status!r}") from err


RequestedStatus = Annotated[LocalStatus, Depends(get_requested_status)]


def _get_db_user(client_dn: str, client_ca: str) -> User:
    """
    Fetch a non-suspended user from the database by certificate DN and CA.

    This function will fetch a user from the database as long as they are not suspended and return
    a validated Pydantic model.

    Args:
        client_dn (str): The client user's DN
        client_ca (str): The client user's CA

    Raises:
        HTTPException (500): If multiple users are found with the same DN and CA.
        HTTPException (403): If no user is found with the specified DN and CA.
        HTTPException (403): If the matching user is suspended.
        HTTPException (500): For unexpected database errors.

    Returns:
        User: The matching user as a validated Pydantic model.
    """
    with sql.managed_session() as session:
        try:
            user = session.scalars(
                select(Users)
                .where(Users.dn == client_dn)
                .where(Users.ca == client_ca)
            ).one()
        except MultipleResultsFound as err:
            raise HTTPException(500, 'Internal Server Error: Duplicate user detected. '
                                     f'user: ({client_dn}, {client_ca})') from err
        except NoResultFound as err:
            raise HTTPException(403, f'Forbidden: Unknown user. user: ({client_dn}, {client_ca})') from err
        except Exception as err:
            raise HTTPException(500, f"Internal Server Error: Unknown Exception caught {type(err)}-> {err}") from err

        if user.suspended:
            raise HTTPException(403, f'Forbidden: User is suspended by VO. user: ({client_dn}, {client_ca})')

        return User.model_validate(user)


def get_verified_user(request: Request) -> User:
    """
    FastAPI dependency: verify the client's certificate headers and return the DB user.

    Returns:
        User: Validated database user matching the verified client certificate.
    """
    required_headers = {'Ssl-Client-S-Dn', 'Ssl-Client-I-Dn', 'Ssl-Client-Verify'}
    missing_headers = required_headers.difference(request.headers)
    if missing_headers:
        raise HTTPException(401, 'Unauthorized: Incomplete certificate information '
                                 f'available, required: {list(missing_headers)}')

    client_dn, client_ca = _apache_client_convert(request.headers['Ssl-Client-S-Dn'],
                                                  request.headers['Ssl-Client-I-Dn'])
    client_verified = request.headers['Ssl-Client-Verify']
    if client_verified != 'SUCCESS':
        raise HTTPException(401, f'Unauthorized: Cert not verified for user DN: {client_dn}, CA: {client_ca}.')

    return _get_db_user(client_dn, client_ca)


VerifiedUser = Annotated[User, Depends(get_verified_user)]


def admin_only(user: VerifiedUser) -> User:
    """
    FastAPI dependency: enforce that the verified user is an admin.

    Returns:
        User: The verified admin user.
    """
    if not user.admin:
        raise HTTPException(403, 'Forbidden: Admin users only')
    return user


AdminUser = Annotated[User, Depends(admin_only)]


DUMMY_USER = Users(id=17,
                   dn='/test/CN=dummy user/testdn',
                   ca='ca',
                   email='test@email.com',
                   suspended=False,
                   admin=True)


def get_dummy_user() -> User:
    """
    Dependency override providing dummy credentials for testing/mock mode.

    Returns:
        User: Pydantic representation of the configured dummy user.
    """
    return _get_db_user(DUMMY_USER.dn, DUMMY_USER.ca)
