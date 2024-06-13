#!/usr/bin/env python3
# pylint: disable=invalid-name
"""Script to start the Production web server."""
# Py2/3 compatibility layer
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *  # pylint: disable=wildcard-import, unused-wildcard-import, redefined-builtin
from future.utils import viewitems

import os
import sys
import argparse
import importlib
import logging
from logging.handlers import TimedRotatingFileHandler
from itertools import chain
from pprint import pformat
import mock
import pkg_resources
import psutil

from productionsystem.utils import expand_path


def stop(args):
    """Stop the webapp."""
    pidfile = args.pid_file
    if not os.path.exists(pidfile):
        logger.error("Pid file '%s' doesn't exist", pidfile)
        return

    try:
        with open(pidfile, 'r') as file_:
            pid = int(file_.read())
    except IOError as err:
        logger.error("Failed to open pid file: %s", err.message)
        return
    except ValueError as err:
        logger.error("Bad pid value in pidfile '%s': %s", pidfile, err.message)
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


def start(args):
    """Start the webapp."""
    # Force clean local DB for mock-mode
    ###########################################################################
    if args.mock_mode:
        dbpath = os.path.join(current_dir, 'requests.db')
        args.dburl = "sqlite:///" + dbpath
        if os.path.exists(dbpath):
            os.remove(dbpath)
        apache_utils = importlib.import_module('productionsystem.apache_utils')
        mock.patch.object(apache_utils, "check_credentials",
                          wraps=apache_utils.dummy_credentials).start()

    # Load WebApp class.
    ###########################################################################
    WebApp = config_instance.entry_point_map['webapp']['daemon'].load()
#    WebApp = pkg_resources.load_entry_point(config.getConfig('Plugins').get('webapp',
#                                                                            'productionsystem'),
#                                            'daemons',
#                                            'webapp')

    # Get extra jinja2 loader if present
    ###########################################################################
    extra_jinja2_loader = config_instance.entry_point_map['webapp'].get('jinja2_loader')
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
           keep_fds=[fhandler.stream.fileno()],
           foreground=args.debug_mode).start()


if __name__ == '__main__':
    current_dir = os.getcwd()
    app_name = os.path.splitext(os.path.basename(__file__))[0]

    parser = argparse.ArgumentParser(description='Run the Production web server.')
    subparser = parser.add_subparsers(title='subcommands', dest="subcommand",
                                      help='use subcommand -h for additional help.')
    start_parser = subparser.add_parser('start', help='start the webserver')
    stop_parser = subparser.add_parser('stop', help='stop the webserver')
    parser.set_defaults(app_name=app_name)
    start_parser.set_defaults(func=start, extension=None)
    stop_parser.set_defaults(func=stop, debug_mode=True, mock_mode=False, extension=None)

    start_parser.add_argument('-v', '--verbose', action='count',
                              help="Increase the logged verbosity, can be used twice")
    stop_parser.add_argument('-v', '--verbose', action='count',
                             help="Increase the logged verbosity, can be used twice")
    start_parser.add_argument('-l', '--log-dir', default=os.path.join(current_dir, 'log'),
                              help="Path to the log directory. Will be created if doesn't exist "
                              "[default: %(default)s]")
    start_parser.add_argument('-d', '--dburl',
                              default="sqlite:///" + os.path.join(current_dir, 'requests.db'),
                              help="URL for the requests DB. Note can use the prefix "
                                   "'mysql+pymysql://' if you have a problem with MySQLdb.py "
                                   "[default: %(default)s]")
    start_parser.add_argument('--socket-host', default='0.0.0.0',
                              help="The host address to listen on (0.0.0.0 means all available "
                              "interfaces) [default: %(default)s]")
    start_parser.add_argument('--socket-port', default=8080, type=int,
                              help="The host port to listen on [default: %(default)s]")
    start_parser.add_argument('--thread-pool', default=8, type=int,
                              help="The number of threads in the pool [default: %(default)s]")
    start_parser.add_argument('--git-schema', default='GITHUB',
                              help="The git schema to use [default: %(default)s]")
    start_parser.add_argument('--git-api-base-url', default='https://api.github.com/repos',
                              help="The git API base url [default: %(default)s]")
    start_parser.add_argument('--git-token', default='',
                              help="The git API access token [default: %(default)s]")
    start_parser.add_argument('-p', '--pid-file',
                              default=os.path.join(current_dir, '%s.pid' % app_name),
                              help="The pid file used by the daemon [default: %(default)s]")
    start_parser.add_argument('-c', '--config',
                              default='~/.config/productionsystem/productionsystem.conf',
                              help="The config file [default: %(default)s]")
    stop_parser.add_argument('-c', '--config',
                             default='~/.config/productionsystem/productionsystem.conf',
                             help="The config file [default: %(default)s]")
    start_parser.add_argument('--debug-mode', action='store_true', default=False,
                              help="Run the daemon in a debug interactive monitoring mode. "
                              "(debugging only)")
    start_parser.add_argument('--mock-mode', action='store_true', default=False,
                              help="Run the daemon with dummy user credentials installed and "
                                   "spoof these credentials when connecting. Also blanks and sets "
                                   "up a fresh local DB with one test job each time daemon starts. "
                              "(debugging only)")
    stop_parser.add_argument('-p', '--pid-file',
                             default=os.path.join(current_dir, '%s.pid' % app_name),
                             help="The pid file used by the daemon [default: %(default)s]")
    projects = set(entry_point.dist.project_name for entry_point in
                   chain(pkg_resources.iter_entry_points('dbmodels'),
                         pkg_resources.iter_entry_points('monitoring'),
                         pkg_resources.iter_entry_points('webapp'),
                         pkg_resources.iter_entry_points('webapp.services')))
    projects -= {'productionsystem'}
    if projects:
        extensions = start_parser.add_argument_group("Extensions")
        extensions.add_argument('--extension', choices=projects,
                                help="Activate the chosen extension")
    args = parser.parse_args()
    cli_args = vars(args).copy()

    # Config Setup
    ###########################################################################
    config_path = expand_path(args.config)
    if not os.path.exists(config_path):
        config_path = None
    config = importlib.import_module('productionsystem.config')
    config_instance = config.ConfigSystem.setup(config_path)
    if config_path is not None:
        arg_dict = vars(args)
        # Lay the config params on top of default parser ones
        arg_dict.update(config_instance.get_section("webapp"))
        # Now parse again with the current namespace to lay non-default parsed params on top
        args = subparser.choices[arg_dict['subcommand']] \
                        .parse_args(sys.argv[2:], namespace=argparse.Namespace(**arg_dict))

    # Logging setup
    ###########################################################################
    # setup the handler
    fhandler = logging.StreamHandler()
    if not args.debug_mode:
        # check and create logging dir
        log_dir = expand_path(args.log_dir)
        if not os.path.isdir(log_dir):
            if os.path.exists(log_dir):
                raise ValueError("%s path already exists and isnt a directory so cant make log dir"
                                 % log_dir)
            os.makedirs(log_dir)

        # use a filehandler
        fhandler = TimedRotatingFileHandler(os.path.join(log_dir, '%s.log' % app_name),
                                            when='midnight', backupCount=5)
    fhandler.setFormatter(logging.Formatter("[%(asctime)s] %(name)15s : "
                                            "%(levelname)8s : "
                                            "%(message)s"))

    # setup the root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(fhandler)
    root_logger.setLevel(max(logging.WARNING - 10 * (args.verbose or 0), logging.DEBUG))

    # setup the main app logger
    logger = logging.getLogger(app_name)
    logger.debug("Script called with args:\n%s", pformat(cli_args))
    if config_path is None:
        logger.warning("Config file '%s' does not exist", cli_args['config'])
    logger.debug("Active config looks like:\n%s", pformat(config_instance.config))
    logger.debug("Runtime args:\n%s", pformat(vars(args)))

    # Entry Point Setup
    ###########################################################################
    entry_point_map = pkg_resources.get_entry_map('productionsystem')
    if args.extension is not None:
        if args.extension not in projects:
            logger.critical("Extension '%s' enabled in config file is not valid, "
                            "expected one of: %s", args.extension, list(projects))
            sys.exit(1)
        for group, map in viewitems(entry_point_map):
            map.update(pkg_resources.get_entry_map(args.extension, group))
    config_instance.entry_point_map = entry_point_map
    logger.debug("Starting with entry point map:\n%s", pformat(entry_point_map))

    # Enact the subcommand
    ###########################################################################
    args.func(args)
