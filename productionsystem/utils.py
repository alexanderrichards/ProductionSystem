"""Package utility module."""
import os
import shutil
from tempfile import NamedTemporaryFile, mkdtemp


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
    for i in xrange(0, len(sequence), nentries):
        yield sequence[i:i + nentries]


# This can derive from ExitStack in Python3
class TemporyFileManagerContext(object):
    """Temporary file/dir manager context."""

    def __init__(self):
        """Initialisation."""
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

    def new_file(self, mode=None, **kwargs):
        """Create a new temporary file."""
        kwargs.pop("delete", None)  # We want to handle deletion.
        file_ = NamedTemporaryFile(**kwargs)
        if mode is not None:
            os.chmod(file_, mode)
        self._files.append(file_)
        return file_

    def new_dir(self, **kwargs):
        """Create a new temporary dir."""
        dir_ = mkdtemp(**kwargs)
        self._dirs.append(dir_)
        return dir_
