"""
Configuration System Module.
"""
from __future__ import annotations

import ast
import configparser
import logging
from collections import defaultdict
from copy import deepcopy
from os.path import abspath, expanduser, expandvars, realpath

from .singleton import singleton


@singleton
class ConfigSystem(object):
    """
    Config system singleton.
    """
    def __init__(self, configs=None):
        """
        Initialise.

        Args:
            configs: Optional config filename or iterable of filenames to read immediately.
        """
        self._config = defaultdict(dict)
        self._logger = logging.getLogger(__name__)
        if configs is not None:
            self.read(configs)

    @property
    def config(self):
        """
        Get the current state of the configuration.

        Returns:
            dict: Deep copy of the current configuration mapping.
        """
        return dict(deepcopy(self._config))

    @property
    def sections(self):
        """
        Get list of sections.

        Returns:
            list[str]: Names of loaded configuration sections.
        """
        return list(self._config)

    @property
    def entry_point_map(self):
        """
        Return the entry point map.

        Returns:
            dict | None: Deep copy of the configured extension entry-point map.
        """
        return deepcopy(self._config['Core'].get("entry_point_map"))

    @entry_point_map.setter
    def entry_point_map(self, map):
        """
        Set the entry point map (one time only).

        Args:
            map: Entry-point mapping discovered from installed projects.
        """
        if self._config['Core'].get("entry_point_map") is not None:
            self._logger.warning("Can not re-set entry_point_map once it's been set.")
        else:
            self._config['Core']['entry_point_map'] = map

    def get_section(self, section):
        """
        Return a given section.

        Args:
            section: Configuration section name to copy.

        Returns:
            dict: Deep copy of the requested section values.
        """
        return deepcopy(self._config[section])

    def read(self, filenames, ignore_errors=False):
        """
        Initialise the configuration system.

        Args:
            filenames: Config filename or iterable of filenames to load.
            ignore_errors: If True, log unreadable or invalid files and continue.

        Returns:
            None. Updates the in-memory configuration from parsed files.

        Raises:
            IOError: If a file cannot be opened and ``ignore_errors`` is False.
            configparser.Error: If a file cannot be parsed and ``ignore_errors`` is False.
        """
        config_parser = configparser.ConfigParser()
        config_parser.optionxform = str

        if isinstance(filenames, str):
            filenames = [filenames]
        filenames = {abspath(realpath(expanduser(expandvars(filename))))
                     for filename in filenames}

        for filename in filenames:
            try:
                with open(filename, 'r') as config_file:
                    config_parser.read_file(config_file)
                self._logger.debug("Read config file: %s", filename)
            except IOError:
                self._logger.warning("Failed to open config file: %r", filename)
                if not ignore_errors:
                    raise
            except configparser.Error:
                self._logger.warning("Failed to read config file: %r", filename)
                if not ignore_errors:
                    raise

        for section in config_parser.sections():
            self._config[section].update((key, ast.literal_eval(val))
                                         for key, val in config_parser.items(section))


def getConfig(section):  # pylint: disable=invalid-name
    """
    Get config helper function.

    Return the config for the given section.

    Args:
        section (str): Configuration section to retrieve.

    Returns:
        dict: A copy of the section configuration.
    """
    return ConfigSystem.get_instance().get_section(section)  # pylint: disable=no-member
