#!/usr/bin/env python
# pylint: disable=invalid-name
"""Dirac daemon run script."""
import os
import sys
import importlib
import argparse
import random
import logging
from logging.handlers import TimedRotatingFileHandler
from itertools import chain
import pkg_resources
import psutil
import mock


from productionsystem.utils import expand_path


def stop(args):
    """Stop the monitoring daemon."""
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
    """Start the monitoring daemon."""

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
        dirac_class_mock = mock.MagicMock
        dirac_class_mock.kill = mock.MagicMock(return_value=None)
        dirac_class_mock.delete = mock.MagicMock(return_value=None)
        dirac_class_mock.status = mock.MagicMock(side_effect=lambda ids: {'OK': True, 'Value': {id: {'Status': 'DONE'} for id in ids}})
        dirac_class_mock.submit = mock.MagicMock(side_effect=lambda jobs: {'OK': True, 'Value': [random.randrange(1234) for _ in xrange(1, len(jobs) +1 )]} if isinstance(jobs, list) else {'OK': True, 'Value': [random.randrange(1234)]})
        dirac_class_mock.reschedule = mock.MagicMock(side_effect=lambda ids: {'OK': True, 'Value': ids})
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
    DiracDaemon = importlib.import_module('productionsystem.monitoring.diracrpc.DiracRPCServer')\
                           .DiracDaemon

    # Daemon setup
    ###########################################################################
    DiracDaemon(address=(args.socket_host, args.socket_port),
                app=app_name,
                pid=args.pid_file,
                logger=logger,
                keep_fds=[fhandler.stream.fileno()],
                foreground=args.debug_mode).start()


if __name__ == '__main__':
    current_dir = os.getcwd()
    app_name = os.path.splitext(os.path.basename(__file__))[0]

    parser = argparse.ArgumentParser(description='Run the DIRAC environment daemon.')
    subparser = parser.add_subparsers(title='subcommands', dest="subcommand",
                                      help='use subcommand -h for additional help.')
    start_parser = subparser.add_parser('start', help='start the monitoring daemon')
    stop_parser = subparser.add_parser('stop', help='stop the monitoring daemon')
    parser.set_defaults(app_name=app_name)
    start_parser.set_defaults(func=start, extension=None)
    stop_parser.set_defaults(func=stop, debug_mode=True, extension=None)

    start_parser.add_argument('--socket-host', default='localhost',
                              help="The dirac environment API host [default: %(default)s]")
    start_parser.add_argument('--socket-port', default=18861, type=int,
                              help="The dirac environment API port [default: %(default)s]")
    start_parser.add_argument('-p', '--pid-file',
                              default=os.path.join(current_dir, "%s.pid" % app_name),
                              help="The pid file used by the daemon [default: %(default)s]")
    stop_parser.add_argument('-p', '--pid-file',
                             default=os.path.join(current_dir, "%s.pid" % app_name),
                             help="The pid file used by the daemon [default: %(default)s]")
    start_parser.add_argument('-l', '--log-dir', default=os.path.join(current_dir, 'log'),
                              help="Path to the log directory. Will be created if doesn't exist "
                                   "[default: %(default)s]")
    start_parser.add_argument('-v', '--verbose', action='count',
                              help="Increase the logged verbosite, can be used twice")
    stop_parser.add_argument('-v', '--verbose', action='count',
                             help="Increase the logged verbosite, can be used twice")
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
                              help="Run the daemon with the DIRAC API mocked away. "
                                   "(debugging only)")
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
    real_config = expand_path(args.config)
    if not os.path.exists(real_config):
        real_config = None
    config = importlib.import_module('productionsystem.config')
    config_instance = config.ConfigSystem.setup(real_config)
    if real_config is not None:
        arg_dict = vars(args)
        arg_dict.update(config_instance.get_section("dirac"))
        args = parser.parse_args(namespace=argparse.Namespace(**arg_dict))

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
    logger.debug("Script called with args: %s", cli_args)
    if real_config is None:
        logger.warning("Config file '%s' does not exist", cli_args['config'])
    logger.debug("Active config looks like: %s", config_instance.config)
    logger.debug("Runtime args: %s", args)

    # Entry Point Setup
    ###########################################################################
    entry_point_map = pkg_resources.get_entry_map('productionsystem')
    if args.extension is not None:
        if args.extension not in projects:
            logger.critical("Extension '%s' enabled in config file is not valid, "
                            "expected one of: %s", args.extension, list(projects))
            sys.exit(1)
        for group, map in entry_point_map.iteritems():
            map.update(pkg_resources.get_entry_map(args.extension, group))
    config_instance.entry_point_map = entry_point_map
    logger.debug("Starting with entry point map: %s", entry_point_map)

    # Enact the subcommand
    ###########################################################################
    args.func(args)
