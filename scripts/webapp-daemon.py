#!/usr/bin/env python
# pylint: disable=invalid-name
"""Script to start the LZ Production web server."""
import os
import argparse
import pkg_resources
import importlib
import logging
from logging.handlers import TimedRotatingFileHandler

from productionsystem.utils import expand_path

if __name__ == '__main__':
    app_name = os.path.splitext(os.path.basename(__file__))[0]
    lzprod_root = os.path.dirname(os.path.dirname(expand_path(__file__)))

    parser = argparse.ArgumentParser(description='Run the LZ production web server.')
    parser.add_argument('-v', '--verbose', action='count',
                        help="Increase the logged verbosite, can be used twice")
    parser.add_argument('-l', '--log-dir', default=os.path.join(lzprod_root, 'log'),
                        help="Path to the log directory. Will be created if doesn't exist "
                             "[default: %(default)s]")
    parser.add_argument('-d', '--dburl',
                        default="sqlite:///" + os.path.join(lzprod_root, 'requests.db'),
                        help="URL for the requests DB. Note can use the prefix 'mysql+pymysql://' "
                             "if you have a problem with MySQLdb.py [default: %(default)s]")
    parser.add_argument('-a', '--socket-host', default='0.0.0.0',
                        help="The host address to listen on (0.0.0.0 means all available "
                             "interfaces) [default: %(default)s]")
    parser.add_argument('-p', '--socket-port', default=8080, type=int,
                        help="The host port to listen on [default: %(default)s]")
    parser.add_argument('-t', '--thread-pool', default=8, type=int,
                        help="The number of threads in the pool [default: %(default)s]")
    parser.add_argument('-i', '--pid-file', default=os.path.join(lzprod_root, 'webserver-daemon.pid'),
                        help="The pid file used by the daemon [default: %(default)s]")
    parser.add_argument('-c', '--config', default='~/.config/productionsystem/productionsystem.conf',
                        help="The config file [default: %(default)s]")
    parser.add_argument('--debug-mode', action='store_true', default=False,
                        help="Run the daemon in a debug interactive monitoring mode. "
                             "(debugging only)")
    args = parser.parse_args()

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
    fhandler = TimedRotatingFileHandler(os.path.join(log_dir, 'webapp-daemon.log'),
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

    # Config Setup
    ###########################################################################
    real_config = expand_path(args.config)
    if not os.path.exists(real_config):
        logger.warning("Config file '%s' does not exist", real_config)
        real_config = None
    config = importlib.import_module('productionsystem.config')
    config.ConfigSystem.setup(real_config)

    # Load WebApp class.
    ###########################################################################
    WebApp = pkg_resources.load_entry_point(config.getConfig('Plugins').get('webapp', 'productionsystem'), 'daemons', 'webapp')

    # Daemon setup
    ###########################################################################
    WebApp(dburl=args.dburl,
           socket_host=args.socket_host,
           socket_port=args.socket_port,
           thread_pool=args.thread_pool,
           app=app_name,
           pid=args.pid_file,
           logger=logger,
           keep_fds=[fhandler.stream.fileno()],
           foreground=args.debug_mode).start()
