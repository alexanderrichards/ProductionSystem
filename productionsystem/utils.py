"""Package utility module."""
# Py2/3 compatibility layer
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *  # pylint: disable=wildcard-import, unused-wildcard-import, redefined-builtin

import os
import shutil
from tempfile import NamedTemporaryFile, mkdtemp
from datetime import datetime


def timestamp():
    """
    Return the current timestamp.

    Returns:
        str: The current timestamp.
    """
    return datetime.now().strftime(r"[%Y-%m-%d %H:%M:%S]")


class TimeStampLogString(str):
    """
    Time stamp log string.

    This is basically a str that adds the timestamp and newline whenever
    a new log string is concatenated.
    """
    def __add__(self, other):
        return TimeStampLogString(super().__add__("%s %s\n" % (timestamp(), other)))


def expand_path(path):
    """Expand filesystem path."""
    return os.path.abspath(os.path.realpath(os.path.expandvars(os.path.expanduser(path))))


def igroup(sequence, nentries):
    """
    Split a sequence into groups.

    Args:
        sequence (Sequence): The sequence to be split
        nentries (int): The number of entries per group

    """
    for i in range(0, len(sequence), nentries):
        yield sequence[i:i + nentries]


# This can derive from ExitStack in Python3
class TemporyFileManagerContext(object):
    """Temporary file/dir manager context."""

    def __init__(self):
        """Initialise."""
        self._files = []
        self._dirs = []

    def __enter__(self):
        """Enter context."""
        return self

    def __exit__(self, *_):
        """
        Exit context.

        This automatically cleans up all temporary files/dirs.
        """
        for file_ in self._files:
            file_.close()
        for dir_ in self._dirs:
            shutil.rmtree(dir_, ignore_errors=True)
        self._files = []
        self._dirs = []

    def new_file(self, permissions=None, **kwargs):
        """Create a new temporary file."""
        kwargs.pop("delete", None)  # We want to handle deletion.
        file_ = NamedTemporaryFile(**kwargs)
        if permissions is not None:
            os.chmod(file_.name, permissions)
        self._files.append(file_)
        return file_

    def new_dir(self, **kwargs):
        """Create a new temporary dir."""
        dir_ = mkdtemp(**kwargs)
        self._dirs.append(dir_)
        return dir_
