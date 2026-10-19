#!/usr/bin/env python
# pylint: disable=invalid-name
"""
Script to read users info from VOMS and update locat SQL table.
"""
from __future__ import annotations

import importlib
import os

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
        cert: str = typer.Option("~/.globus/usercert.pem"),
        key: str = typer.Option("~/.globus/userkey.pem"),
        verbose: int = typer.Option(0, "-v", "--verbose", count=True),
        dburl: str = typer.Option(
            "sqlite:///" + os.path.join(os.getcwd(), "requests.db"), "-d", "--dburl"),
        verify: bool = typer.Option(False, help="Verify the VOMS server."),
        config: str = typer.Option(DEFAULT_CONFIG, "-c", "--config"),
        trusted_cas: str = typer.Option("", help="Trusted CA bundle or directory."),
):
    """
    Synchronize the user database with VOMS.

    Args:
        ctx: Typer context used when applying config-file defaults.
        voms: Root URL of the VOMS SOAP services.
        cert: Client certificate path for VOMS requests.
        key: Client private-key path paired with ``cert``.
        verbose: Count of ``-v`` flags controlling log verbosity.
        dburl: SQLAlchemy database URL for the user table.
        verify: Whether to verify the VOMS server certificate.
        config: Path to the ProductionSystem configuration file.
        trusted_cas: CA bundle or directory overriding ``verify`` when provided.
    """
    from sqlalchemy import exists, or_, select, update  # pylint: disable=import-outside-toplevel
    from sqlalchemy.exc import IntegrityError, SQLAlchemyError  # pylint: disable=import-outside-toplevel

    values = locals()
    values.pop("ctx")
    args, cli_args, config_instance, config_path = prepare_options(
        ctx, "userdb", values, APP_NAME)
    if args.trusted_cas:
        args.verify = os.path.expandvars(os.path.expanduser(args.trusted_cas))
    logger = setup_logging(
        args, cli_args, config_instance, config_path, daemon=False)

    # Do work
    ###########################################################################
    registry = importlib.import_module('productionsystem.sql.registry')
    Users = importlib.import_module('productionsystem.sql.models.Users').Users
    Requests = importlib.import_module('productionsystem.sql.models.Requests').Requests
    ParametricJobs = importlib.import_module('productionsystem.sql.models.ParametricJobs').ParametricJobs
    DiracJobs = importlib.import_module('productionsystem.sql.models.DiracJobs').DiracJobs
    CertClient = importlib.import_module('productionsystem.suds_utils').CertClient

    # Note if clients share the same transport we get a
    # 'Duplicate domain "suds.options" found' exception.
    headers = {"Content-Type": "text/xml;charset=UTF-8",
               "SOAPAction": "",
               'X-VOMS-CSRF-GUARD': '1'}
    cert_key = (os.path.expandvars(os.path.expanduser(args.cert)), os.path.expandvars(os.path.expanduser(args.key)))
    vomsAdmin = CertClient(os.path.join(args.voms, 'VOMSAdmin?wsdl'),
                           cert=cert_key,
                           headers=headers, verify=args.verify)
    vomsCompat = CertClient(os.path.join(args.voms, 'VOMSCompatibility?wsdl'),
                            cert=cert_key,
                            headers=headers, verify=args.verify)

    voms_users_info = vomsAdmin.service.listMembers(vomsAdmin.service.getVOName())
    voms_valid_users = set(vomsCompat.service.getGridmapUsers())

    # Fetch both lists before writing; empty snapshots must not disable or delete every account.
    if not voms_users_info or not voms_valid_users:
        logger.error("VOMS returned an empty membership or gridmap list; "
                     "aborting user synchronisation without database changes.")
        raise typer.Exit(code=1)

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

        # Retain owners of historical records, but prevent login when absent from VOMS.
        for removed_user in removed_users:
            has_history = session.scalar(
                select(or_(
                    exists().where(Requests.requester_id == removed_user.id),
                    exists().where(ParametricJobs.requester_id == removed_user.id),
                    exists().where(DiracJobs.requester_id == removed_user.id),
                ))
            )
            if has_history:
                logger.info("Suspending user absent from VOMS with retained history: DN='%s', CA='%s'",
                            removed_user.dn, removed_user.ca)
                removed_user.suspended = True
                continue

            try:
                # Keep foreign keys enforced; a savepoint isolates concurrent history creation.
                with session.begin_nested():
                    session.delete(removed_user)
                    session.flush()
            except IntegrityError as err:
                original_error = err.orig
                is_foreign_key_error = (
                    original_error.args[:1] == (1451,)  # MySQL/MariaDB parent-row deletion
                    or getattr(original_error, "sqlite_errorname", None) == "SQLITE_CONSTRAINT_FOREIGNKEY"
                    or getattr(original_error, "sqlstate", None) == "23503"  # PostgreSQL
                    or getattr(original_error, "pgcode", None) == "23503"
                )
                if not is_foreign_key_error:
                    raise
                logger.warning("User gained database references during deletion; suspending instead: "
                               "DN='%s', CA='%s': %s", removed_user.dn, removed_user.ca, err)
                removed_user.suspended = True
            else:
                logger.info("Deleted user absent from VOMS without history: DN='%s', CA='%s'",
                            removed_user.dn, removed_user.ca)

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
                        update(Users)
                        .where(Users.dn == voms_dn)
                        .where(Users.ca == voms_ca)
                        .values(email=voms_email)
                    )
                except SQLAlchemyError as err:
                    logger.error("Error updateing user email: %s", err)

            if voms_suspended != db_suspended:
                logger.info("Updating user: DN='%s', CA='%s', Suspended=%s->%s",
                            voms_dn, voms_ca, db_suspended, voms_suspended)
                try:
                    session.execute(
                        update(Users)
                        .where(Users.dn == voms_dn)
                        .where(Users.ca == voms_ca)
                        .values(suspended=voms_suspended)
                    )
                except SQLAlchemyError as err:
                    logger.error("Error updating user suspended status: %s", err)

    import logging  # pylint: disable=import-outside-toplevel
    logging.shutdown()


if __name__ == '__main__':
    app()
