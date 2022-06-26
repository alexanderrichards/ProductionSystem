"""Utilities for Jinja2."""
# Py2/3 compatibility layer
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *  # pylint: disable=wildcard-import, unused-wildcard-import, redefined-builtin # noqa: F401, F403

import jinja2
import hashlib

from productionsystem.singleton import singleton


def jinja2_filter(filt):
    """
    Create Jinja2 filter.

    Decorator to load a custom filter into Jinja2.
    Args:
        filt (function): A Jinja2 filter function.
    Returns:
        function: The filter function.

    """
    jinja2.filters.FILTERS[filt.__name__] = filt
    return filt


def get_template_env(extra_jinja2_loader):
    loader = jinja2.PackageLoader("productionsystem.webapp")
    if extra_jinja2_loader is not None:
        prefix_loader = jinja2.PrefixLoader({'productionsystem': loader})
        loader = jinja2.ChoiceLoader([prefix_loader,
                                      extra_jinja2_loader,
                                      loader])
    template_env = jinja2.Environment(loader=loader)
    template_env.globals["get_flashed_messages"] = get_flashed_messages
    return template_env


@jinja2_filter
def gravitar_hash(email_add):
    """
    Hash an email address.

    Generate a gravitar compatible hash from an email address.
    Args:
        email_add (str): The target email address
    Returns:
        str: The hash string

    """
    return hashlib.md5(email_add.strip().lower().encode("utf-8")).hexdigest()


@jinja2_filter
def service_badge_url(service, service_name):
    """Return ShieldIO url for service badge."""
    name = service_name
    from productionsystem.sql.enums import ServiceStatus
    status = ServiceStatus.UNKNOWN
    if service is not None:
        name = service.name
        status = service.status
    return "https://img.shields.io/badge/{name}-{status.name}-{status.value}.svg"\
        .format(name=name, status=status)


@jinja2_filter
def log_splitter(log):
    """Split up the log string by line."""
    if log is None:
        return []
    return log.splitlines()


MESSAGES = []


def get_flashed_messages():
    pass


@singleton
class MessageQueue(object):
    def __init__(self):
        self._queue = []
        pass

    def get_flashed_messages(self):
        tmp, self._queue = self._queue[:], []
        return tmp
