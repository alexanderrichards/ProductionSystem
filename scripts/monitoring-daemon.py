#!/usr/bin/env python
# pylint: disable=invalid-name
"""
DB monitoring daemon.

Daemon that monitors the DB and creates Ganga jobs from new requests. It
also runs the Ganga monitoring loop to keep Ganga jobs up to date.
"""
import os
import sys
import argparse
import importlib
import logging
from logging.handlers import TimedRotatingFileHandler
from itertools import chain
import pkg_resources
import psutil

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

    # Modify the verify arg based on trusted_cas path
    if args.trusted_cas:
        args.verify = args.trusted_cas

    # Dynamic imports to module level
    ###########################################################################
    # Add the python src path to the sys.path for future imports
    # sys.path.append(lzprod_root)
    MonitoringDaemon = config_instance.entry_point_map['monitoring']['daemon'].load()

    # Daemon setup
    ###########################################################################
    MonitoringDaemon(dburl=args.dburl,
                     delay=args.frequency,
                     cert=(args.cert, args.key),
                     verify=args.verify,
                     app=args.app_name,
                     pid=args.pid_file,
                     logger=logger,
                     keep_fds=[fhandler.stream.fileno()],
                     foreground=args.debug_mode).start()


if __name__ == '__main__':
    current_dir = os.getcwd()
    app_name = os.path.splitext(os.path.basename(__file__))[0]

    parser = argparse.ArgumentParser(description='Run the job monitoring daemon.')
    subparser = parser.add_subparsers(title='subcommands', dest="subcommand",
                                      help='use subcommand -h for additional help.')
    start_parser = subparser.add_parser('start', help='start the monitoring daemon')
    stop_parser = subparser.add_parser('stop', help='stop the monitoring daemon')
    parser.set_defaults(app_name=app_name)
    start_parser.set_defaults(func=start, extension=None)
    stop_parser.set_defaults(func=stop, debug_mode=True, extension=None)

    start_parser.add_argument('-f', '--frequency', default=5, type=int,
                              help="The frequency that the daemon does it's main functionality "
                                   "(in mins) [default: %(default)s]")
    start_parser.add_argument('-p', '--pid-file',
                              default=os.path.join(current_dir, "%s.pid" % app_name),
                              help="The pid file used by the daemon [default: %(default)s]")
    stop_parser.add_argument('-p', '--pid-file',
                             default=os.path.join(current_dir, "%s.pid" % app_name),
                             help="The pid file used by the daemon [default: %(default)s]")
    start_parser.add_argument('-l', '--log-dir', default=os.path.join(current_dir, 'log'),
                              help="Path to the log directory. Will be created if doesn't exist "
                                   "[default: %(default)s]")
    start_parser.add_argument('-c', '--config',
                              default='~/.config/productionsystem/productionsystem.conf',
                              help="The config file [default: %(default)s]")
    stop_parser.add_argument('-c', '--config',
                             default='~/.config/productionsystem/productionsystem.conf',
                             help="The config file [default: %(default)s]")
    start_parser.add_argument('--cert', default=os.path.expanduser('~/.globus/usercert.pem'),
                              help='Path to cert .pem file [default: %(default)s]')
    start_parser.add_argument('--key', default=os.path.expanduser('~/.globus/userkey.pem'),
                              help='Path to key .pem file. Note must be an unencrypted key. '
                                   '[default: %(default)s]')
    start_parser.add_argument('-v', '--verbose', action='count',
                              help="Increase the logged verbosite, can be used twice")
    stop_parser.add_argument('-v', '--verbose', action='count',
                             help="Increase the logged verbosite, can be used twice")
    start_parser.add_argument('-d', '--dburl',
                              default="sqlite:///" + os.path.join(current_dir, 'requests.db'),
                              help="URL for the requests DB. Note can use the prefix "
                                   "'mysql+pymysql://' if you have a problem with MySQLdb.py "
                                   "[default: %(default)s]")
    start_parser.add_argument('--verify', default=False, action="store_true",
                              help="Verify the DIRAC server.")
    start_parser.add_argument('--trusted-cas', default='',
                              help="Path to the trusted CA_BUNDLE file or directory containing the "
                                   "certificates of trusted CAs. Note if set to a directory, the "
                                   "directory must have been processed using the c_rehash utility "
                                   "supplied with OpenSSL. If using a CA_BUNDLE file can also "
                                   "consider using the REQUESTS_CA_BUNDLE environment variable "
                                   "instead (this may cause pip to fail to validate against PyPI). "
                                   "This option implies and superseeds -y")
    start_parser.add_argument('--debug-mode', action='store_true', default=False,
                              help="Run the daemon in a debug interactive monitoring mode. "
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
    logger.debug("Script called with args: %s", args)

    # Config Setup
    ###########################################################################
    real_config = expand_path(args.config)
    if not os.path.exists(real_config):
        logger.warning("Config file '%s' does not exist", real_config)
        real_config = None
    config = importlib.import_module('productionsystem.config')
    config_instance = config.ConfigSystem.setup(real_config)
    logger.debug("Active config looks like: %s", config_instance.config)

    # Entry Point Setup
    ###########################################################################
    config_extension = config_instance.get_section("Core").get("extension")
    entry_point_map = pkg_resources.get_entry_map('productionsystem')
    if args.extension is not None:
        for group, map in entry_point_map.iteritems():
            map.update(pkg_resources.get_entry_map(args.extension, group))
    elif config_extension is not None:
        if config_extension not in projects:
            logger.critical("Extension '%s' enabled in config file is not valid, "
                            "expected one of: %s", config_extension, list(projects))
            sys.exit(1)
        for group, map in entry_point_map.iteritems():
            map.update(pkg_resources.get_entry_map(config_extension, group))
    config_instance.entry_point_map = entry_point_map
    logger.debug("Starting with entry point map: %s", entry_point_map)

    # Enact the subcommand
    ###########################################################################
    args.func(args)
