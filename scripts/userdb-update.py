#!/usr/bin/env python
# pylint: disable=invalid-name
"""Script to read users info from VOMS and update locat SQL table."""
from __future__ import annotations

import os
import importlib

import typer

from productionsystem.cli import prepare_options, setup_logging

app = typer.Typer(help="Read users from VOMS and update the local database.")
APP_NAME = "userdb-update"
DEFAULT_CONFIG = "~/.config/productionsystem/productionsystem.conf"


@app.command()
def update_users(
        ctx: typer.Context,
        voms: str = typer.Option(
            "https://voms.gridpp.ac.uk:8443/voms/lz/services",
            help="Root URL of the VOMS services."),
        cert: str = typer.Option(os.path.expanduser("~/.globus/usercert.pem")),
        key: str = typer.Option(os.path.expanduser("~/.globus/userkey.pem")),
        verbose: int = typer.Option(0, "-v", "--verbose", count=True),
        dburl: str = typer.Option(
            "sqlite:///" + os.path.join(os.getcwd(), "requests.db"), "-d", "--dburl"),
        verify: bool = typer.Option(False, help="Verify the VOMS server."),
        config: str = typer.Option(DEFAULT_CONFIG, "-c", "--config"),
        trusted_cas: str = typer.Option("", help="Trusted CA bundle or directory."),
):
    """Synchronize the user database with VOMS."""
    from sqlalchemy import select  # pylint: disable=import-outside-toplevel
    from sqlalchemy.exc import SQLAlchemyError  # pylint: disable=import-outside-toplevel

    values = locals()
    values.pop("ctx")
    args, cli_args, config_instance, config_path = prepare_options(
        ctx, "userdb", values, APP_NAME)
    if args.trusted_cas:
        args.verify = args.trusted_cas
    logger = setup_logging(
        args, cli_args, config_instance, config_path, daemon=False)

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
        db_users = set(session.scalars(select(Users)).all())

        new_users = voms_users.difference(db_users)
        removed_users = db_users.difference(voms_users)
        common_users = db_users.intersection(voms_users)  # takes from arg first

        # Add new users in VOMS
        for new_user in new_users:
            logger.info("Adding user: DN='%s', CA='%s'", new_user.dn, new_user.ca)
            try:
                session.add(new_user)
            except SQLAlchemyError as err:
                logger.error("Error Adding user: %s", err)

        # Remove users removed from VOMS
        for removed_user in removed_users:
            logger.info("Removing user: DN='%s', CA='%s'", removed_user.dn, removed_user.ca)
            try:
                session.execute(
                    select(Users)
                    .where(Users.dn == removed_user.dn)
                    .where(Users.ca == removed_user.ca)
                ).delete(synchronize_session=False)
            except SQLAlchemyError as err:
                logger.error("Error deleting user: %s", err)

        # Users with modified suspended status, update from VOMS
        for common_user in common_users:
            voms_dn, voms_ca = common_user.dn, common_user.ca
            voms_email, voms_suspended = common_user.email, common_user.suspended
            db_email, db_suspended = session.execute(
                                        select(Users.email, Users.suspended)
                                        .where(Users.dn == voms_dn)
                                        .where(Users.ca == voms_ca)
                                        ).one()

            if voms_email != db_email:
                logger.info("Updating user: DN='%s', CA='%s', Email=%s->%s",
                            voms_dn, voms_ca, db_email, voms_email)
                try:
                    session.execute(
                        select(Users)
                        .where(Users.dn == voms_dn)
                        .where(Users.ca == voms_ca)
                        ).update({'email': voms_email})
                except SQLAlchemyError as err:
                    logger.error("Error updateing user email: %s", err)

            if voms_suspended != db_suspended:
                logger.info("Updating user: DN='%s', CA='%s', Suspended=%s->%s",
                            voms_dn, voms_ca, db_suspended, voms_suspended)
                try:
                    session.execute(
                        select(Users)
                        .where(Users.dn == voms_dn)
                        .where(Users.ca == voms_ca)
                        ).update({'suspended': voms_suspended})
                except SQLAlchemyError as err:
                    logger.error("Error updating user suspended status: %s", err)

    import logging  # pylint: disable=import-outside-toplevel
    logging.shutdown()


if __name__ == '__main__':
    app()
