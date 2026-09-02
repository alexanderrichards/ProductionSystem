#!/usr/bin/env python
# pylint: disable=invalid-name
"""Dirac daemon run script."""
from __future__ import annotations

import os
import sys
import importlib
import random

import typer
import unittest.mock as mock

from productionsystem.cli import prepare_options, setup_logging, stop_daemon

app = typer.Typer(help="Run the DIRAC environment daemon.", no_args_is_help=True)
APP_NAME = "dirac-daemon"
DEFAULT_CONFIG = "~/.config/productionsystem/productionsystem.conf"
DEFAULT_PID_FILE = os.path.join(os.getcwd(), APP_NAME + ".pid")
DEFAULT_LOG_DIR = os.path.join(os.getcwd(), "log")


def stop(args, *, logger):
    """Stop the monitoring daemon."""
    stop_daemon(args.pid_file, logger)


def start(args, *, logger):
    """Start the dirac daemon."""
    if args.mock_mode:
        mock.patch.dict(sys.modules, {"DIRAC": mock.MagicMock(),
                                      "DIRAC.Core": mock.MagicMock(),
                                      "DIRAC.Core.Base": mock.MagicMock(),
                                      "DIRAC.Core.Base.Script": mock.MagicMock(),
                                      "DIRAC.Core.DISET": mock.MagicMock(),
                                      "DIRAC.Core.DISET.RPCClient": mock.MagicMock(),
                                      "DIRAC.Interfaces": mock.MagicMock(),
                                      "DIRAC.Interfaces.API": mock.MagicMock(),
                                      "DIRAC.Interfaces.API.Job": mock.MagicMock(),
                                      "DIRAC.Interfaces.API.Dirac": mock.MagicMock()}).start()
        dirac_job_mock = mock.MagicMock
        dirac_job_mock.setInputSandbox = mock.MagicMock(return_value=None)
        dirac_job_mock._setParamValue = mock.MagicMock(return_value=None)
        dirac_class_mock = mock.MagicMock
        dirac_class_mock.killJob = mock.MagicMock(return_value=None)
        dirac_class_mock.deleteJob = mock.MagicMock(return_value=None)
        dirac_class_mock.getJobStatus = mock.MagicMock(side_effect=lambda ids: {'OK': True, 'Value': {id: {'Status': 'DONE'} for id in ids}})
        dirac_class_mock.submitJob = mock.MagicMock(side_effect=lambda jobs: {'OK': True, 'Value': [random.randrange(1234) for _ in range(1, len(jobs) +1 )]} if isinstance(jobs, list) else {'OK': True, 'Value': [random.randrange(1234)]})
        dirac_class_mock.rescheduleJob = mock.MagicMock(side_effect=lambda ids: {'OK': True, 'Value': ids})
        dirac_rpc_mock = mock.MagicMock
        dirac_rpc_mock.listDirectory = mock.MagicMock(side_effect=lambda directory_path, _: {'OK': True, 'Value':{'Failed': [], 'Successful': {directory_path: {'Files': {'FileA': {}, 'FileB': {}, 'FileC': {}}}}}})
        sys.modules['DIRAC.Interfaces.API.Job'].Job = dirac_job_mock
        sys.modules['DIRAC.Interfaces.API.Dirac'].Dirac = dirac_class_mock
        sys.modules['DIRAC.Core.DISET.RPCClient'].RPCClient = dirac_rpc_mock

    # DIRAC will parse our command line args unless we remove them
    sys.argv = sys.argv[:1]
    Script = importlib.import_module('DIRAC.Core.Base.Script')
    Script.parseCommandLine(ignoreErrors=True)

    # Dynamic imports to module level
    ###########################################################################
    # Add the python src path to the sys.path for future imports
    # sys.path.append(lzprod_root)
    DiracDaemon = importlib.import_module('productionsystem.monitoring.diracrest.DiracRESTDaemon')\
                           .DiracDaemon

    # Daemon setup
    ###########################################################################
    DiracDaemon(address=(args.api_host, args.api_port),
                app=args.app_name,
                pid=args.pid_file,
                logger=logger,
                keep_fds=[handler.stream.fileno() for handler in logger.handlers],
                foreground=args.debug_mode).start()


def _run(ctx, section, values, action):
    values.pop("ctx", None)
    args, cli_values, config_instance, config_path = prepare_options(
        ctx, section, values, APP_NAME)
    logger = setup_logging(
        args, cli_values, config_instance, config_path, daemon=True)
    action(args, logger=logger)


@app.command("start")
def start_command(
        ctx: typer.Context,
        api_host: str = typer.Option("localhost", help="DIRAC API host."),
        api_port: int = typer.Option(18861, help="DIRAC API port."),
        pid_file: str = typer.Option(DEFAULT_PID_FILE, "-p", "--pid-file"),
        log_dir: str = typer.Option(DEFAULT_LOG_DIR, "-l", "--log-dir"),
        verbose: int = typer.Option(0, "-v", "--verbose", count=True),
        config: str = typer.Option(DEFAULT_CONFIG, "-c", "--config"),
        debug_mode: bool = typer.Option(False, help="Run in the foreground."),
        mock_mode: bool = typer.Option(False, help="Mock the DIRAC API."),
        extension: str | None = typer.Option(None, help="Activate an installed extension."),
):
    """Start the DIRAC daemon."""
    _run(ctx, "dirac", locals() | {"debug_mode": debug_mode}, start)


@app.command("stop")
def stop_command(
        ctx: typer.Context,
        pid_file: str = typer.Option(DEFAULT_PID_FILE, "-p", "--pid-file"),
        verbose: int = typer.Option(0, "-v", "--verbose", count=True),
        config: str = typer.Option(DEFAULT_CONFIG, "-c", "--config"),
):
    """Stop the DIRAC daemon."""
    values = locals() | {"debug_mode": True, "log_dir": ""}
    _run(ctx, "dirac", values, stop)


if __name__ == '__main__':
    app()
