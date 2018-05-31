"""Package utility module."""
import os


def expand_path(path):
    """Expand filesystem path."""
    return os.path.abspath(os.path.realpath(os.path.expandvars(os.path.expanduser(path))))
