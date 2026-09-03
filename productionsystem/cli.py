"""Shared helpers for ProductionSystem command-line applications."""
from __future__ import annotations

import importlib.metadata as importmeta
import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pprint import pformat
from types import SimpleNamespace

import click
import typer

from productionsystem.config import ConfigSystem
from productionsystem.singleton import InstantiationError
from productionsystem.utils import expand_path

ENTRY_POINT_GROUPS = ('dbmodels', 'monitoring', 'webapp', 'webapp.services')


def load_entry_points():
    """Load ProductionSystem and extension entry points."""
    discovered = {}
    entry_points = importmeta.entry_points()
    if isinstance(entry_points, dict):  # older Python 3.11 compatible code
        entry_points = [ep for group in entry_points.values() for ep in group]

    for entry_point in entry_points:
        if entry_point.group in ENTRY_POINT_GROUPS:
            project = entry_point.module.split('.')[0]
            discovered.setdefault(project, {}).setdefault(
                entry_point.group, {})[entry_point.name] = entry_point

    entry_point_map = discovered.get('productionsystem', {})
    projects = set(discovered).difference(('productionsystem',))
    for project in projects:
        entry_point_map.update(discovered[project])
    return entry_point_map, projects


def prepare_options(ctx, section, values, app_name):
    """Apply config-file defaults and initialize extension entry points."""
    cli_values = dict(values)
    config_path = expand_path(values['config'])
    existing_config_path = config_path if os.path.exists(config_path) else None
    try:
        config_instance = ConfigSystem.setup(existing_config_path)
    except InstantiationError:
        config_instance = ConfigSystem.get_instance()
        if existing_config_path is not None:
            config_instance.read(existing_config_path)

    if existing_config_path is not None:
        for name, value in config_instance.get_section(section).items():
            if name in values and _is_default_source(ctx.get_parameter_source(name)):
                values[name] = value

    entry_point_map, projects = load_entry_points()
    extension = values.get('extension')
    if extension is not None and extension not in projects:
        choices = ", ".join(sorted(projects)) or "none installed"
        raise typer.BadParameter(
            "Unknown extension %r; available extensions: %s" % (extension, choices),
            param_hint="--extension",
        )
    config_instance.entry_point_map = entry_point_map
    values['app_name'] = app_name
    return SimpleNamespace(**values), cli_values, config_instance, existing_config_path


def _is_default_source(source):
    return getattr(source, "name", None) == "DEFAULT"


def setup_logging(args, cli_values, config_instance, config_path, daemon=False):
    """Configure logging and return the application logger."""
    if daemon:
        handler = logging.StreamHandler()
        if not args.debug_mode:
            log_dir = expand_path(args.log_dir)
            if not os.path.isdir(log_dir):
                if os.path.exists(log_dir):
                    raise ValueError(
                        "%s exists and is not a directory" % log_dir)
                os.makedirs(log_dir)
            handler = TimedRotatingFileHandler(
                os.path.join(log_dir, '%s.log' % args.app_name),
                when='midnight',
                backupCount=5,
            )
        handler.setFormatter(logging.Formatter(
            "[%(asctime)s] %(name)15s : %(levelname)8s : %(message)s"))
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        root_logger.setLevel(max(
            logging.WARNING - 10 * (args.verbose or 0), logging.DEBUG))
    else:
        logging.basicConfig(
            level=max(logging.WARNING - 10 * (args.verbose or 0), logging.DEBUG),
            format="[%(asctime)s] %(name)15s : %(levelname)8s : %(message)s",
        )

    logger = logging.getLogger(args.app_name)
    logger.debug("Script called with args:\n%s", pformat(cli_values))
    if config_path is None:
        logger.warning("Config file '%s' does not exist", cli_values['config'])
    logger.debug("Active config looks like:\n%s", pformat(config_instance.config))
    logger.debug("Runtime args:\n%s", pformat(vars(args)))
    logger.debug("Starting with entry point map:\n%s",
                 pformat(config_instance.entry_point_map))
    return logger


def stop_daemon(pid_file, logger):
    """Stop a daemon identified by a PID file."""
    import psutil  # pylint: disable=import-outside-toplevel

    if not os.path.exists(pid_file):
        logger.error("Pid file '%s' doesn't exist", pid_file)
        return

    try:
        with open(pid_file, 'r') as file_:
            pid = int(file_.read())
    except IOError as err:
        logger.error("Failed to open pid file: %s", err)
        return
    except ValueError as err:
        logger.error("Bad pid value in pidfile '%s': %s", pid_file, err)
        return

    if not psutil.pid_exists(pid):
        logger.warning("No process with pid: %d running", pid)
        return

    logger.info("Sending daemon SIGTERM...")
    daemon = psutil.Process(pid)
    daemon.terminate()
    try:
        daemon.wait(timeout=1)
    except psutil.TimeoutExpired:
        logger.warning("Daemon not responding, sending SIGKILL...")
        daemon.kill()
        try:
            daemon.wait(timeout=0)
        except psutil.TimeoutExpired:
            logger.warning("SIGKILL failed to remove the process!")
    logging.shutdown()
