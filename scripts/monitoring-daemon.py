#!/usr/bin/env python
# pylint: disable=invalid-name
"""
DB monitoring daemon.

Daemon that monitors the DB and creates Ganga jobs from new requests. It
also runs the Ganga monitoring loop to keep Ganga jobs up to date.
"""
from __future__ import annotations

import os

import typer

from productionsystem.cli import prepare_options, setup_logging, stop_daemon
from productionsystem.config import ConfigSystem

app = typer.Typer(help="Run the job monitoring daemon.", no_args_is_help=True)
APP_NAME = "monitoring-daemon"
DEFAULT_CONFIG = "~/.config/productionsystem/productionsystem.conf"
DEFAULT_PID_FILE = os.path.join(os.getcwd(), APP_NAME + ".pid")
DEFAULT_LOG_DIR = os.path.join(os.getcwd(), "log")


def stop(args, *, logger):
    """
    Stop the monitoring daemon.

    Args:
        args: Prepared CLI options containing PID file and monitoring settings.
        logger: Logger used for daemon lifecycle messages.
    """
    stop_daemon(args.pid_file, logger)


def start(args, *, logger):
    """
    Start the monitoring daemon.

    Args:
        args: Prepared CLI options used to configure and start monitoring.
        logger: Logger passed to the monitoring daemon.
    """
    # Modify the verify arg based on trusted_cas path
    if args.trusted_cas:
        args.verify = args.trusted_cas

    # Dynamic imports to module level
    ###########################################################################
    # Add the python src path to the sys.path for future imports
    # sys.path.append(lzprod_root)

    entry_point_map = ConfigSystem.get_instance().entry_point_map

    MonitoringDaemon = entry_point_map['monitoring']['daemon'].load()

    # Daemon setup
    ###########################################################################
    MonitoringDaemon(dburl=args.dburl,
                     delay=args.frequency,
                     cert=(args.cert, args.key),
                     verify=args.verify,
                     app=args.app_name,
                     pid=args.pid_file,
                     logger=logger,
                     keep_fds=[handler.stream.fileno() for handler in logger.handlers],
                     foreground=args.debug_mode).start()


def _run(ctx, values, action):
    """
    Run a monitoring daemon lifecycle action with parsed CLI values.
    
    Args:
        ctx: Typer context used when applying config-file defaults.
        values: Parsed command option values.
        action: Lifecycle function to execute after setup.
    """
    values.pop("ctx", None)
    args, cli_values, config_instance, config_path = prepare_options(
        ctx, "monitoring", values, APP_NAME)
    logger = setup_logging(
        args, cli_values, config_instance, config_path, daemon=True)
    action(args, logger=logger)


@app.command("start")
def start_command(
        ctx: typer.Context,
        frequency: int = typer.Option(5, "-f", "--frequency", help="Polling frequency in minutes."),
        pid_file: str = typer.Option(DEFAULT_PID_FILE, "-p", "--pid-file"),
        log_dir: str = typer.Option(DEFAULT_LOG_DIR, "-l", "--log-dir"),
        config: str = typer.Option(DEFAULT_CONFIG, "-c", "--config"),
        cert: str = typer.Option(os.path.expanduser("~/.globus/usercert.pem")),
        key: str = typer.Option(os.path.expanduser("~/.globus/userkey.pem")),
        verbose: int = typer.Option(0, "-v", "--verbose", count=True),
        dburl: str = typer.Option(
            "sqlite:///" + os.path.join(os.getcwd(), "requests.db"), "-d", "--dburl"),
        verify: bool = typer.Option(False, help="Verify the DIRAC server."),
        trusted_cas: str = typer.Option("", help="Trusted CA bundle or directory."),
        debug_mode: bool = typer.Option(False, help="Run in the foreground."),
        extension: str | None = typer.Option(None, help="Activate an installed extension."),
):
    """
    Start the monitoring daemon.

    Args:
        ctx: Typer context used when applying config-file defaults.
        frequency: Monitoring polling interval in minutes.
        pid_file: Path to the daemon PID file.
        log_dir: Directory for daemon log files.
        config: Path to the ProductionSystem configuration file.
        cert: Client certificate path for DIRAC/VOMS HTTP calls.
        key: Client private-key path paired with ``cert``.
        verbose: Count of ``-v`` flags controlling log verbosity.
        dburl: SQLAlchemy database URL monitored by the daemon.
        verify: Whether to verify remote TLS certificates.
        trusted_cas: CA bundle or directory overriding ``verify`` when provided.
        debug_mode: If True, run in the foreground.
        extension: Optional installed extension name to activate.
    """
    _run(ctx, locals(), start)


@app.command("stop")
def stop_command(
        ctx: typer.Context,
        pid_file: str = typer.Option(DEFAULT_PID_FILE, "-p", "--pid-file"),
        verbose: int = typer.Option(0, "-v", "--verbose", count=True),
        config: str = typer.Option(DEFAULT_CONFIG, "-c", "--config"),
):
    """
    Stop the monitoring daemon.

    Args:
        ctx: Typer context used when applying config-file defaults.
        pid_file: Path to the daemon PID file.
        verbose: Count of ``-v`` flags controlling log verbosity.
        config: Path to the ProductionSystem configuration file.
    """
    _run(ctx, locals() | {"debug_mode": True, "log_dir": ""}, stop)


if __name__ == '__main__':
    app()
