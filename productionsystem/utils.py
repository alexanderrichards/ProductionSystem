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
    def __init__(self):
        self._files = []
        self._dirs = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        for file_ in self._files:
            file_.close()
        for dir_ in self._dirs:
            shutil.rmtree(dir_, ignore_errors=True)
        self._files = []
        self._dirs = []

    def new_file(self):
        file_ = NamedTemporaryFile()
        self._files.append(file_)
        return file_

    def new_dir(self):
        dir_ = mkdtemp()
        self._dirs.append(dir_)
        return dir_
