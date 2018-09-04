#!/usr/bin/env python
# pylint: disable=invalid-name
"""Dirac daemon run script."""
import os
import sys
import importlib
import argparse
import logging
from logging.handlers import TimedRotatingFileHandler

from DIRAC.Core.Base import Script

from productionsystem.utils import expand_path

if __name__ == '__main__':
    app_name = os.path.splitext(os.path.basename(__file__))[0]
    lzprod_root = os.path.dirname(os.path.dirname(expand_path(__file__)))

    parser = argparse.ArgumentParser(description='Run the DIRAC environment daemon.')
    parser.add_argument('-s', '--host', default='localhost',
                        help="The dirac environment API host [default: %(default)s]")
    parser.add_argument('-p', '--port', default=18861, type=int,
                        help="The dirac environment API port [default: %(default)s]")
    parser.add_argument('-f', '--pid-file', default=os.path.join(lzprod_root, app_name + '.pid'),
                        help="The pid file used by the daemon [default: %(default)s]")
    parser.add_argument('-l', '--log-dir', default=os.path.join(lzprod_root, 'log'),
                        help="Path to the log directory. Will be created if doesn't exist "
                             "[default: %(default)s]")
    parser.add_argument('-v', '--verbose', action='count',
                        help="Increase the logged verbosite, can be used twice")
    parser.add_argument('--debug-mode', action='store_true', default=False,
                        help="Run the daemon in a debug interactive monitoring mode. "
                             "(debugging only)")
    args = parser.parse_args()

    # DIRAC will parse our command line args unless we remove them
    sys.argv = sys.argv[:1]
    Script.parseCommandLine(ignoreErrors=True)

    # Logging setup
    ###########################################################################
    # check and create logging dir
    log_dir = expand_path(args.log_dir)
    if not os.path.isdir(log_dir):
        if os.path.exists(log_dir):
            raise ValueError("%s path already exists and is not a directory so cant make log dir"
                             % log_dir)
        os.makedirs(log_dir)

    # setup the handler
    fhandler = TimedRotatingFileHandler(os.path.join(log_dir, 'dirac-daemon.log'),
                                        when='midnight', backupCount=5)
    if args.debug_mode:
        fhandler = logging.StreamHandler()
    fhandler.setFormatter(logging.Formatter("[%(asctime)s] %(name)15s : %(levelname)8s : %(message)s"))

    # setup the root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(fhandler)
    root_logger.setLevel(max(logging.WARNING - 10 * (args.verbose or 0), logging.DEBUG))

    # setup the main app logger
    logger = logging.getLogger(app_name)
    logger.debug("Script called with args: %s", args)

    # Dynamic imports to module level
    ###########################################################################
    # Add the python src path to the sys.path for future imports
    sys.path.append(lzprod_root)
    DiracDaemon = importlib.import_module('productionsystem.monitoring.diracrpc.DiracRPCServer').DiracDaemon

    # Daemon setup
    ###########################################################################
    DiracDaemon(address=(args.host, args.port),
                app=app_name,
                pid=args.pid_file,
                logger=logger,
                keep_fds=[fhandler.stream.fileno()],
                foreground=args.debug_mode).start()
