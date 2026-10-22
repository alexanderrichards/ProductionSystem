"""
Package utility module.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from contextlib import ExitStack
from pathlib import Path
from typing import IO, Any, Sequence, Generator
from datetime import datetime, timezone
from tempfile import NamedTemporaryFile, TemporaryDirectory
try:
    from typing import override
except ImportError:  # unfortunately DIRAC we are using is on Python 3.11 still.
    def override(func):
        return func


def timestamp() -> str:
    """
    Return the current timestamp.

    Returns:
        str: The current timestamp.
    """
    return datetime.now(timezone.utc).strftime(r"[%Y-%m-%d %H:%M:%S]")


def expand_path(path: str) -> str:
    """
    Expand filesystem path.

    Returns:
        str: Absolute path with user, environment, and symlink components resolved.

    Args:
        path (str): The filesystem path to expand.
    """
    return os.path.abspath(os.path.realpath(os.path.expandvars(os.path.expanduser(path))))


def igroup(sequence: Sequence[Any], nentries: int) -> Generator[Sequence[Any]]:
    """
    Split a sequence into groups.

    Args:
        sequence (Sequence[Any]): The sequence to be split
        nentries (int): The number of entries per group

    Returns:
        Generator[Sequence[Any]]: Groups of the sequence with the specified number of entries.

    """
    for i in range(0, len(sequence), nentries):
        yield sequence[i:i + nentries]


class ITemporaryManager(ABC):
    @abstractmethod
    def new_file(self, filename: str | Path | None = None, *, permissions: int | None = None, **kwargs) -> IO[Any]:
        raise NotImplementedError()

    @abstractmethod
    def new_dir(self, *, ignore_cleanup_errors: bool = True, **kwargs) -> ManagerAwareTemporaryDirectory:
        raise NotImplementedError()



class TemporaryManagerContext(ExitStack, ITemporaryManager):
    """
    Temporary file/dir manager context.
    """

    def _cleanup_named_file(self, fileobj: IO[Any], filepath: Path):
        """
        Close and delete the given fileobj.

        Args:
            fileobj (IO[Any]): the file object to close
            filepath (Path): the path to delete
        """
        fileobj.close()
        if filepath.exists():
            filepath.unlink(missing_ok=True)

    @override
    def new_file(self, filename: str | Path | None = None, *, permissions: int | None = None, **kwargs) -> IO[Any]:
        """
        Create a new temporary file managed by this context.

        Args:
            filename (str | Path | None): Optional filename for the temporary file. Defaults to None.
            permissions (int | None): Optional filesystem mode to apply to the created file.
                                      Should be in octal format (e.g., 0o644).
            **kwargs: Options forwarded to ``NamedTemporaryFile``.

        Returns:
            file object: Open temporary file object.
        """
        # can do either of these. I'm not sure which is most efficient, but this ensures that we
        # always deleted on context exit or deletion
        #
        # if {"delete", "delete_on_close"} & kwargs.keys():
        #     raise ValueError("Cannot specify 'delete' or 'delete_on_close' when using new_file.")
        if 'delete' in kwargs or 'delete_on_close' in kwargs:
            raise ValueError("Cannot specify 'delete' or 'delete_on_close' when using new_file.")

        if filename is not None:
            filtered_kwargs = {k: v for k, v in kwargs.items() if k in {'mode',
                                                                        'buffering',
                                                                        'encoding',
                                                                        'errors',
                                                                        'newline',
                                                                        'closefd',
                                                                        'opener'}}
            prefix = kwargs.pop('prefix', '')
            suffix = kwargs.pop('suffix', '')
            filtered_kwargs.setdefault('mode', 'x+b')
            filepath: Path = Path(f"{prefix}{filename}{suffix}")
            if (dir := kwargs.pop('dir', None)) is not None:
                filepath = Path(dir) / filepath
            new_file = open(filepath, **filtered_kwargs)
            self.callback(self._cleanup_named_file, new_file, filepath)
        else:
            new_file = self.enter_context(NamedTemporaryFile(delete=True, delete_on_close=True, **kwargs))

        if permissions is not None:
            os.chmod(new_file.name, permissions)

        return new_file

    @override
    def new_dir(self, *, ignore_cleanup_errors: bool = True, **kwargs) -> ManagerAwareTemporaryDirectory:
        """
        Create a new temporary directory managed by this context.

        Args:
            ignore_cleanup_errors: Whether to ignore errors during cleanup of the temporary directory. Defaults to True.
            **kwargs: Options forwarded to ``TemporaryDirectory`` except ``ignore_cleanup_errors``.

        Returns:
            ManagerAwareTemporaryDirectory: Path to the temporary directory.
        """
        if "delete" in kwargs:
            raise ValueError("Cannot specify 'delete' when using new_dir.")
        dir_manager = ManagerAwareTemporaryDirectory(delete=True,
                                                     ignore_cleanup_errors=ignore_cleanup_errors,
                                                     manager=self,
                                                     **kwargs)
        # TemporaryDirectory returns the path str from it's enter so can't return it directly
        self.enter_context(dir_manager)
        return dir_manager

class ManagerAwareTemporaryDirectory(TemporaryDirectory, ITemporaryManager):
    def __init__(self, *args, manager, **kwargs):
        """
        Initialize a ManagerAwareTemporaryDirectory.

        Args:
            *args: Positional arguments forwarded to TemporaryDirectory.
            manager (ITemporaryManager): The manager responsible for this temporary directory.
            **kwargs: Keyword arguments forwarded to TemporaryDirectory.
        """
        super().__init__(*args, **kwargs)
        self._manager = manager


    @override
    def new_file(self, filename: str | Path | None = None, *, permissions: int | None = None, **kwargs) -> IO[Any]:
        """
        Create a new temporary file managed by this context.

        Args:
            filename (str | Path | None): Name of the temporary file. Defaults to None.
            permissions(int | None): Optional filesystem mode. Defaults to None.
            **kwargs: Options forwarded to ``NamedTemporaryFile``.

        Returns:
            IO[Any]: Open temporary file object.
        """
        kwargs['dir'] = self.name
        return self._manager.new_file(filename, permissions=permissions, **kwargs)

    @override
    def new_dir(self, *, ignore_cleanup_errors: bool = True, **kwargs) -> ManagerAwareTemporaryDirectory:
        """
        Create a new temporary directory managed by this context.

        Args:
            ignore_cleanup_errors: Whether to ignore errors during cleanup of the temporary directory. Defaults to True.
            **kwargs: Options forwarded to ``TemporaryDirectory`` except ``ignore_cleanup_errors``.

        Returns:
            ManagerAwareTemporaryDirectory: Path to the temporary directory.
        """
        kwargs['dir'] = self.name
        return self._manager.new_dir(ignore_cleanup_errors=ignore_cleanup_errors, **kwargs)
