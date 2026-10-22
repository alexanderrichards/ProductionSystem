"""
Status enums for use in SQL tables.

Define service health, external DIRAC states, and local request states. Map
DIRAC states to the local lifecycle through ``STATUS_MAP``.
"""
from __future__ import annotations

from enum import Enum, IntEnum, unique

__all__ = ('ServiceStatus', 'DiracStatus', 'LocalStatus', 'STATUS_MAP')


@unique
class ServiceStatus(Enum):
    """
    Service Status Enum.

    Attributes:
        UNKNOWN (str): Unavailable health information; badge color light grey.
        DOWN (str): Unhealthy service; badge color red.
        UP (str): Healthy service; badge color bright green.
    """
    UNKNOWN = 'lightgrey'
    DOWN = 'red'
    UP = 'brightgreen'  # pylint: disable=invalid-name


@unique
class DiracStatus(IntEnum):
    """
    DIRAC Status Enum.

    Represent external job states with stable integer values. The
    ``local_status`` property groups these detailed states into the local
    request lifecycle using ``STATUS_MAP``; in particular, ``DONE`` is locally
    completed while DIRAC's ``COMPLETED`` still maps to running.
    """
    UNKNOWN = 0
    DELETED = 1
    KILLED = 2
    DONE = 3
    COMPLETED = 4
    FAILED = 5
    STALLED = 6
    RUNNING = 7
    SUBMITTING = 8
    RECEIVED = 9
    QUEUED = 10
    WAITING = 11
    CHECKING = 12
    MATCHED = 13
    COMPLETING = 14
    RESCHEDULED = 15

    @property
    def local_status(self):
        """
        Convert to LocalStatus.

        Returns:
            LocalStatus: Local request status corresponding to this DIRAC status.
        """
        return STATUS_MAP[self]


@unique
class LocalStatus(IntEnum):
    """
    Local Status Enum.

    Represent request and parametric-job lifecycle states with stable integers.
    Include approval, submission, execution, removal, and post-production
    checking and closure states used by the database and API.
    """
    REQUESTED = 0
    UNKNOWN = 1
    DELETED = 2
    KILLED = 3
    CLOSED = 12
    CHECKED = 11
    COMPLETED = 4
    FAILED = 5
    APPROVED = 6
    SUBMITTED = 7
    SUBMITTING = 8
    RUNNING = 9
    REMOVING = 10


STATUS_MAP = {DiracStatus.UNKNOWN: LocalStatus.UNKNOWN,
              DiracStatus.DELETED: LocalStatus.DELETED,
              DiracStatus.KILLED: LocalStatus.KILLED,
              DiracStatus.DONE: LocalStatus.COMPLETED,
              DiracStatus.COMPLETED: LocalStatus.RUNNING,
              DiracStatus.COMPLETING: LocalStatus.RUNNING,
              DiracStatus.FAILED: LocalStatus.FAILED,
              DiracStatus.STALLED: LocalStatus.FAILED,
              DiracStatus.RUNNING: LocalStatus.RUNNING,
              DiracStatus.SUBMITTING: LocalStatus.SUBMITTING,
              DiracStatus.RECEIVED: LocalStatus.SUBMITTED,
              DiracStatus.QUEUED: LocalStatus.SUBMITTED,
              DiracStatus.WAITING: LocalStatus.SUBMITTED,
              DiracStatus.CHECKING: LocalStatus.SUBMITTED,
              DiracStatus.MATCHED: LocalStatus.SUBMITTED,
              DiracStatus.RESCHEDULED: LocalStatus.SUBMITTING}
