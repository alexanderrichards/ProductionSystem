#!/usr/bin/env python
# pylint: disable=invalid-name
"""Script to start the Production web server."""
from __future__ import annotations

import importlib
import os
import unittest.mock as mock

import typer

from productionsystem.cli import prepare_options, setup_logging, stop_daemon
from productionsystem.config import ConfigSystem

app = typer.Typer(help="Run the Production web server.", no_args_is_help=True)
APP_NAME = "webapp-daemon"
DEFAULT_CONFIG = "~/.config/productionsystem/productionsystem.conf"
DEFAULT_PID_FILE = os.path.join(os.getcwd(), APP_NAME + ".pid")
DEFAULT_LOG_DIR = os.path.join(os.getcwd(), "log")


def stop(args, *, logger):
    """Stop the webapp."""
    stop_daemon(args.pid_file, logger)


def start(args, *, logger):
    """Start the webapp."""
    # Force clean local DB for mock-mode
    ###########################################################################
    if args.mock_mode:
        dbpath = os.path.join(os.getcwd(), 'requests.db')
        args.dburl = "sqlite:///" + dbpath
        if os.path.exists(dbpath):
            os.remove(dbpath)
        apache_utils = importlib.import_module('productionsystem.apache_utils')  # must load after config entrypoints loaded
        mock.patch.object(apache_utils, "check_credentials",
                          wraps=apache_utils.dummy_credentials).start()

    entry_point_map = ConfigSystem.get_instance().entry_point_map

    # Load WebApp class.
    ###########################################################################
    WebApp = entry_point_map['webapp']['daemon'].load()
#    WebApp = config_instance.entry_point_map['webapp']['daemon'].load()
#    WebApp = pkg_resources.load_entry_point(config.getConfig('Plugins').get('webapp',
#                                                                            'productionsystem'),
#                                            'daemons',
#                                            'webapp')

    # Get extra jinja2 loader if present
    ###########################################################################
    extra_jinja2_loader = entry_point_map['webapp'].get('jinja2_loader')
    if extra_jinja2_loader is not None:
        extra_jinja2_loader = extra_jinja2_loader.load()

    # Daemon setup
    ###########################################################################
    WebApp(dburl=args.dburl,
           socket_host=args.socket_host,
           socket_port=args.socket_port,
           thread_pool=args.thread_pool,
           git_schema=args.git_schema,
           git_token=args.git_token,
           git_api_base_url=args.git_api_base_url,
           extra_jinja2_loader=extra_jinja2_loader,
           mock_mode=args.mock_mode,
           app=args.app_name,
           pid=args.pid_file,
           logger=logger,
           keep_fds=[handler.stream.fileno() for handler in logger.handlers],
           foreground=args.debug_mode).start()


def _run(ctx, values, action):
    values.pop("ctx", None)
    args, cli_values, config_instance, config_path = prepare_options(
        ctx, "webapp", values, APP_NAME)
    logger = setup_logging(
        args, cli_values, config_instance, config_path, daemon=True)
    action(args, logger=logger)


@app.command("start")
def start_command(
        ctx: typer.Context,
        verbose: int = typer.Option(0, "-v", "--verbose", count=True),
        log_dir: str = typer.Option(DEFAULT_LOG_DIR, "-l", "--log-dir"),
        dburl: str = typer.Option(
            "sqlite:///" + os.path.join(os.getcwd(), "requests.db"), "-d", "--dburl"),
        socket_host: str = typer.Option("0.0.0.0", help="Host address to listen on."),
        socket_port: int = typer.Option(8080, help="Port to listen on."),
        thread_pool: int = typer.Option(8, help="Number of server threads."),
        git_schema: str = typer.Option("GITHUB", help="Git service schema."),
        git_api_base_url: str = typer.Option(
            "https://api.github.com/repos", help="Git API base URL."),
        git_token: str = typer.Option("", help="Git API access token."),
        pid_file: str = typer.Option(DEFAULT_PID_FILE, "-p", "--pid-file"),
        config: str = typer.Option(DEFAULT_CONFIG, "-c", "--config"),
        debug_mode: bool = typer.Option(False, help="Run in the foreground."),
        mock_mode: bool = typer.Option(False, help="Run with mock credentials and data."),
        extension: str | None = typer.Option(None, help="Activate an installed extension."),
):
    """Start the web server."""
    _run(ctx, locals(), start)


@app.command("stop")
def stop_command(
        ctx: typer.Context,
        verbose: int = typer.Option(0, "-v", "--verbose", count=True),
        pid_file: str = typer.Option(DEFAULT_PID_FILE, "-p", "--pid-file"),
        config: str = typer.Option(DEFAULT_CONFIG, "-c", "--config"),
):
    """Stop the web server."""
    _run(ctx, locals() | {
        "debug_mode": True,
        "mock_mode": False,
        "log_dir": "",
    }, stop)


if __name__ == '__main__':
    app()
