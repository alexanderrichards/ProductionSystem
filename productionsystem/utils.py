"""
Package utility module.
"""
from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from tempfile import NamedTemporaryFile, mkdtemp


def timestamp():
    """
    Return the current timestamp.

    Returns:
        str: The current timestamp.
    """
    return datetime.now(timezone.utc).strftime(r"[%Y-%m-%d %H:%M:%S]")


def expand_path(path):
    """
    Expand filesystem path.

    Returns:
        str: Absolute path with user, environment, and symlink components resolved.
    """
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


# TODO: This can derive from ExitStack in Python3
class TemporaryFileManagerContext(object):
    """
    Temporary file/dir manager context.
    """
    def __init__(self):
        """
        Initialise.
        """
        self._files = []
        self._dirs = []

    def __enter__(self):
        """
        Enter context.

        Returns:
            TemporaryFileManagerContext: Context manager that owns created temp files and directories.
        """
        return self

    def __exit__(self, *_):
        """
        Exit context.

        This automatically cleans up all temporary files/dirs.

        Args:
            *_: Exception details supplied by the context manager protocol.
        """
        for file_ in self._files:
            file_.close()
        for dir_ in self._dirs:
            shutil.rmtree(dir_, ignore_errors=True)
        self._files = []
        self._dirs = []

    def new_file(self, permissions=None, **kwargs):
        """
        Create a new temporary file.

        Args:
            permissions: Optional filesystem mode to apply to the created file.
            **kwargs: Options forwarded to ``NamedTemporaryFile`` except ``delete``.

        Returns:
            file object: Open temporary file registered for cleanup on context exit.
        """
        kwargs.pop("delete", None)  # We want to handle deletion.
        file_ = NamedTemporaryFile(**kwargs)
        if permissions is not None:
            os.chmod(file_.name, permissions)
        self._files.append(file_)
        return file_

    def new_dir(self, **kwargs):
        """
        Create a new temporary dir.

        Args:
            **kwargs: Options forwarded to ``mkdtemp``.

        Returns:
            str: Path to a temporary directory registered for cleanup on context exit.
        """
        dir_ = mkdtemp(**kwargs)
        self._dirs.append(dir_)
        return dir_
