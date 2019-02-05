#!/usr/bin/env python
# pylint: disable=invalid-name
"""Script to read users info from VOMS and update locat SQL table."""
import os
import logging
import argparse
import importlib
import pkg_resources

from sqlalchemy.exc import SQLAlchemyError

from productionsystem.utils import expand_path

if __name__ == '__main__':
    current_dir = os.getcwd()
    app_name = os.path.splitext(os.path.basename(__file__))[0]

    parser = argparse.ArgumentParser(description='Read list of users from VOMS and update '
                                                 'local table.')
    parser.add_argument('--voms', default='https://voms.hep.wisc.edu:8443/voms/lz/services',
                        help='Root path of VOMS server services. [default: %(default)s]')
    parser.add_argument('--cert', default=os.path.expanduser('~/.globus/usercert.pem'),
                        help='Path to cert .pem file [default: %(default)s]')
    parser.add_argument('--key', default=os.path.expanduser('~/.globus/userkey.pem'),
                        help='Path to key .pem file. Note must be an unencrypted key. '
                             '[default: %(default)s]')
    parser.add_argument('-v', '--verbose', action='count',
                        help="Increase the logged verbosite, can be used twice")
    parser.add_argument('-d', '--dburl',
                        default="sqlite:///" + os.path.join(current_dir, 'requests.db'),
                        help="URL for the requests DB. Note can use the prefix 'mysql+pymysql://' "
                             "if you have a problem with MySQLdb.py [default: %(default)s]")
    parser.add_argument('--verify', default=False, action="store_true",
                        help="Verify the VOMS server.")
    parser.add_argument('-c', '--config',
                        default='~/.config/productionsystem/productionsystem.conf',
                        help="The config file [default: %(default)s]")
    parser.add_argument('--trusted-cas', default='',
                        help="Path to the trusted CA_BUNDLE file or directory containing the "
                             "certificates of trusted CAs. Note if set to a directory, the "
                             "directory must have been processed using the c_rehash utility "
                             "supplied with OpenSSL. If using a CA_BUNDLE file can also consider "
                             "using the REQUESTS_CA_BUNDLE environment variable instead (this may "
                             "cause pip to fail to validate against PyPI). This option implies and "
                             "superseeds --verify")
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
        arg_dict.update(config_instance.get_section("userdb"))
        args = parser.parse_args(namespace=argparse.Namespace(**arg_dict))
    if args.trusted_cas:
        args.verify = args.trusted_cas

    # Logging setup
    ###########################################################################
    # setup the root logger
    logging.basicConfig(level=max(logging.WARNING - 10 * (args.verbose or 0), logging.DEBUG),
                        format="[%(asctime)s] %(name)15s : %(levelname)8s : %(message)s")

    # setup the main app logger
    logger = logging.getLogger(app_name)
    logger.debug("Script called with args: %s", cli_args)
    if config_path is None:
        logger.warning("Config file '%s' does not exist", cli_args['config'])
    logger.debug("Active config looks like: %s", config_instance.config)
    logger.debug("Runtime args: %s", args)

    # Entry Point Setup
    ###########################################################################
    entry_point_map = pkg_resources.get_entry_map('productionsystem')
    config_instance.entry_point_map = entry_point_map
    logger.debug("Starting with entry point map: %s", entry_point_map)

    # Do work
    ###########################################################################
    registry = importlib.import_module('productionsystem.sql.registry')
    Users = importlib.import_module('productionsystem.sql.models.Users').Users
    CertClient = importlib.import_module('productionsystem.suds_utils').CertClient

    # Note if clients share the same transport we get a
    # 'Duplicate domain "suds.options" found' exception.
    headers = {"Content-Type": "text/xml;charset=UTF-8",
               "SOAPAction": "",
               'X-VOMS-CSRF-GUARD': '1'}
    vomsAdmin = CertClient(os.path.join(args.voms, 'VOMSAdmin?wsdl'),
                           cert=(args.cert, args.key),
                           headers=headers, verify=args.verify)
    vomsCompat = CertClient(os.path.join(args.voms, 'VOMSCompatibility?wsdl'),
                            cert=(args.cert, args.key),
                            headers=headers, verify=args.verify)

    voms_users_info = vomsAdmin.service.listMembers(vomsAdmin.service.getVOName())
    voms_valid_users = set(vomsCompat.service.getGridmapUsers())

    voms_users = {Users(dn=user_info['DN'],
                        ca=user_info['CA'],
                        email=user_info['mail'],
                        suspended=user_info['DN'] not in voms_valid_users,
                        admin=False) for user_info in voms_users_info}

    registry.SessionRegistry.setup(args.dburl)
    with registry.managed_session() as session:
        db_users = set(session.query(Users).all())

        new_users = voms_users.difference(db_users)
        removed_users = db_users.difference(voms_users)
        common_users = db_users.intersection(voms_users)  # takes from arg first

        # Add new users in VOMS
        for new_user in new_users:
            logger.info("Adding user: DN='%s', CA='%s'", new_user.dn, new_user.ca)
            try:
                session.add(new_user)
            except SQLAlchemyError as err:
                logger.error("Error Adding user: %s", err.message)

        # Remove users removed from VOMS
        for removed_user in removed_users:
            logger.info("Removing user: DN='%s', CA='%s'", removed_user.dn, removed_user.ca)
            try:
                session.query(Users)\
                       .filter_by(dn=removed_user.dn, ca=removed_user.ca)\
                       .delete(synchronize_session=False)
            except SQLAlchemyError as err:
                logger.error("Error deleting user: %s", err.message)

        # Users with modified suspended status, update from VOMS
        for common_user in common_users:
            voms_dn, voms_ca = common_user.dn, common_user.ca
            voms_email, voms_suspended = common_user.email, common_user.suspended
            db_email, db_suspended = session.query(Users.email, Users.suspended)\
                                            .filter_by(dn=voms_dn, ca=voms_ca)\
                                            .one()

            if voms_email != db_email:
                logger.info("Updating user: DN='%s', CA='%s', Email=%s->%s",
                            voms_dn, voms_ca, db_email, voms_email)
                try:
                    session.query(Users)\
                           .filter_by(dn=voms_dn, ca=voms_ca)\
                           .update({'email': voms_email})
                except SQLAlchemyError as err:
                    logger.error("Error updateing user email: %s", err.message)

            if voms_suspended != db_suspended:
                logger.info("Updating user: DN='%s', CA='%s', Suspended=%s->%s",
                            voms_dn, voms_ca, db_suspended, voms_suspended)
                try:
                    session.query(Users)\
                           .filter_by(dn=voms_dn, ca=voms_ca)\
                           .update({'suspended': voms_suspended})
                except SQLAlchemyError as err:
                    logger.error("Error updating user suspended status: %s", err.message)

    logging.shutdown()
