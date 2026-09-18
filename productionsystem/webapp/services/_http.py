"""Shared FastAPI HTTP helpers for the webapp services."""
from __future__ import annotations

from contextlib import contextmanager

from fastapi import HTTPException


@contextmanager
def http_error_handle(exc_type, status_code, detail):
    """
    Convert a caught exception into an HTTPException.

    A direct replacement for cherrypy.HTTPError.handle: run the body and, if
    exc_type is raised, re-raise it as an HTTPException with the given status
    code and detail message, chained from the original exception.

    Args:
        exc_type (Exception or tuple): The exception type(s) to catch.
        status_code (int): The HTTP status code to respond with.
        detail (str): The error detail message.

    """
    try:
        yield
    except exc_type as err:
        raise HTTPException(status_code=status_code, detail=detail) from err
