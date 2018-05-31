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

from productionsystem.utils import expand_path

if __name__ == '__main__':
    app_name = os.path.splitext(os.path.basename(__file__))[0]
    lzprod_root = os.path.dirname(os.path.dirname(expand_path(__file__)))

    parser = argparse.ArgumentParser(description='Run the job monitoring daemon.')
    parser.add_argument('-f', '--frequency', default=5, type=int,
                        help="The frequency that the daemon does it's main functionality (in mins) "
                             "[default: %(default)s]")
    parser.add_argument('-p', '--pid-file', default=os.path.join(lzprod_root, app_name + '.pid'),
                        help="The pid file used by the daemon [default: %(default)s]")
    parser.add_argument('-l', '--log-dir', default=os.path.join(lzprod_root, 'log'),
                        help="Path to the log directory. Will be created if doesn't exist "
                             "[default: %(default)s]")
    parser.add_argument('-c', '--config', default='~/.config/productionsystem/productionsystem.conf',
                        help="The config file [default: %(default)s]")
    parser.add_argument('-r', '--cert', default=os.path.expanduser('~/.globus/usercert.pem'),
                        help='Path to cert .pem file [default: %(default)s]')
    parser.add_argument('-k', '--key', default=os.path.expanduser('~/.globus/userkey.pem'),
                        help='Path to key .pem file. Note must be an unencrypted key. '
                             '[default: %(default)s]')
    parser.add_argument('-v', '--verbose', action='count',
                        help="Increase the logged verbosite, can be used twice")
    parser.add_argument('-d', '--dburl',
                        default="sqlite:///" + os.path.join(lzprod_root, 'requests.db'),
                        help="URL for the requests DB. Note can use the prefix 'mysql+pymysql://' "
                             "if you have a problem with MySQLdb.py [default: %(default)s]")
    parser.add_argument('-y', '--verify', default=False, action="store_true",
                        help="Verify the DIRAC server.")
    parser.add_argument('-t', '--trusted-cas', default='',
                        help="Path to the trusted CA_BUNDLE file or directory containing the "
                             "certificates of trusted CAs. Note if set to a directory, the "
                             "directory must have been processed using the c_rehash utility "
                             "supplied with OpenSSL. If using a CA_BUNDLE file can also consider "
                             "using the REQUESTS_CA_BUNDLE environment variable instead (this may "
                             "cause pip to fail to validate against PyPI). This option implies and "
                             "superseeds -y")
    parser.add_argument('--debug-mode', action='store_true', default=False,
                        help="Run the daemon in a debug interactive monitoring mode. "
                             "(debugging only)")
    args = parser.parse_args()

    real_config = expand_path(args.config)
    if not os.path.exists(real_config):
        logging.warning("Config file '%s' does not exist")
        real_config = None
    config = importlib.import_module('productionsystem.config')
    config.ConfigSystem.setup(real_config)

    # Modify the verify arg based on trusted_cas path
    if args.trusted_cas:
        args.verify = args.trusted_cas

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
    fhandler = TimedRotatingFileHandler(os.path.join(log_dir, 'monitoring-daemon.log'),
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
    MonitoringDaemon = importlib.import_module('productionsystem.monitoring.MonitoringDaemon')\
                                .MonitoringDaemon

    # Daemon setup
    ###########################################################################
    daemon = MonitoringDaemon(dburl=args.dburl,
                              delay=args.frequency,
                              cert=(args.cert, args.key),
                              verify=args.verify,
                              app=app_name,
                              pid=args.pid_file,
                              logger=logger,
                              keep_fds=[fhandler.stream.fileno()],
                              foreground=args.debug_mode)
    daemon.start()
