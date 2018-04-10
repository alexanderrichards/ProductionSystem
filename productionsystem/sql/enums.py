"""Status enums for use in SQL tables."""
from enum import unique, IntEnum


__all__ = ('DiracStatus', 'LocalStatus', 'STATUS_MAP')


@unique
class DiracStatus(IntEnum):
    """DIRAC Status Enum."""

    UNKNOWN = 0
    DELETED = 1
    KILLED = 2
    DONE = 3
    COMPLETED = 4
    FAILED = 5
    STALLED = 6
    RUNNING = 7
    RECEIVED = 8
    QUEUED = 9
    WAITING = 10
    CHECKING = 11
    MATCHED = 12

    @classmethod
    def members_names(cls):
        """Return list of all enum members names."""
        return cls.__members__.keys()

    @property
    def local_status(self):
        """Convert to LocalStatus."""
        return STATUS_MAP[self]


@unique
class LocalStatus(IntEnum):
    """Local Status Enum."""

    UNKNOWN = 0
    DELETED = 1
    KILLED = 2
    COMPLETED = 3
    FAILED = 4
    REQUESTED = 5
    APPROVED = 6
    SUBMITTED = 7
    SUBMITTING = 8
    RUNNING = 9

    @classmethod
    def members_names(cls):
        """Return list of all enum members names."""
        return cls.__members__.keys()

STATUS_MAP = {DiracStatus.UNKNOWN: LocalStatus.UNKNOWN,
              DiracStatus.DELETED: LocalStatus.DELETED,
              DiracStatus.KILLED: LocalStatus.KILLED,
              DiracStatus.DONE: LocalStatus.COMPLETED,
              DiracStatus.COMPLETED: LocalStatus.RUNNING,
              DiracStatus.FAILED: LocalStatus.FAILED,
              DiracStatus.STALLED: LocalStatus.FAILED,
              DiracStatus.RUNNING: LocalStatus.RUNNING,
              DiracStatus.RECEIVED: LocalStatus.SUBMITTED,
              DiracStatus.QUEUED: LocalStatus.SUBMITTED,
              DiracStatus.WAITING: LocalStatus.SUBMITTED,
              DiracStatus.CHECKING: LocalStatus.SUBMITTED,
              DiracStatus.MATCHED: LocalStatus.SUBMITTED}
