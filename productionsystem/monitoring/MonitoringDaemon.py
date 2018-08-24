"""Monitoring Daemon."""
import logging
import time
from datetime import datetime

import requests
from daemonize import Daemonize
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from productionsystem.sql.registry import SessionRegistry, managed_session
from productionsystem.sql.models import Requests, Services
from productionsystem.sql.enums import LocalStatus, ServiceStatus

MINS = 60


class MonitoringDaemon(Daemonize):
    """Monitoring Daemon."""

    def __init__(self, dburl, delay, cert, verify=False, **kwargs):
        """Initialisation."""
        super(MonitoringDaemon, self).__init__(action=self.main, **kwargs)
        self._dburl = dburl
        self._delay = delay
        self.cert = cert
        self.verify = verify

    def exit(self):
        """Update the monitoringd status on exit."""
        try:
            monitoring_service = Services.get_services(service_name="monitoringd")
        except NoResultFound:
            self.logger.warning("No monitoringd service found. Adding new one")
            try:
                Services(name="monitoringd", status=ServiceStatus.DOWN).add()
            except SQLAlchemyError as err:
                self.logger.exception("Error adding new monitoringd status to DB: %s", err.message)
        except MultipleResultsFound:
            self.logger.error("Multiple services named 'monitoringd'. This needs investigating.")
        else:
            try:
                monitoring_service.status = ServiceStatus.DOWN
                monitoring_service.update()
            except SQLAlchemyError as err:
                self.logger.exception("Error updating the status of monitoring daemon: %s",
                                      err.message)
        super(MonitoringDaemon, self).exit()

    def main(self):
        """Daemon main function."""
        SessionRegistry.setup(self._dburl)

        try:
            while True:
                self.check_services()
                self.monitor_requests()
                time.sleep(self._delay * MINS)
        except Exception:
            self.logger.exception("Unhandled exception while running daemon.")

    def check_services(self):
        """
        Check the status of the services.

        This function checks the status of the DIRAC status as well as updating the
        timestamp for the current monitoringd service.
        """
        services = {service.name: service for service in Services.get_services()}

        # DIRAC
        status = ServiceStatus.DOWN
        if requests.get("https://dirac.gridpp.ac.uk/DIRAC/",
                        cert=self.cert, verify=self.verify) \
                .status_code == 200:
            status = ServiceStatus.UP
        if 'DIRAC' in services:
            dirac_service = services['DIRAC']
            dirac_service.status = status
            try:
                dirac_service.update()
            except SQLAlchemyError as err:
                self.logger.exception("Error updating DIRAC service status: %s", err.message)
        else:
            try:
                Services(name="DIRAC", status=status).add()
            except SQLAlchemyError as err:
                self.logger.exception("Error adding new DIRAC service: %s", err.message)

        # monitoringd
        if 'monitoringd' in services:
            monitoringd_service = services['monitoringd']
            monitoringd_service.status = ServiceStatus.UP
            try:
                monitoringd_service.update()
            except SQLAlchemyError as err:
                self.logger.exception("Error updating monitoringd service status: %s", err.message)
        else:
            try:
                Services(name="monitoringd", status=ServiceStatus.UP).add()
            except SQLAlchemyError as err:
                self.logger.exception("Error adding new monitoringd service: %s", err.message)

    def monitor_requests(self):
        """
        Monitor the DB requests.

        Check the status of ongoing DB requests and either update them or
        create new Ganga tasks for new requests.
        """
        monitored_requests = Requests.get_requests(status=(LocalStatus.APPROVED,
                                                           LocalStatus.SUBMITTED,
                                                           LocalStatus.RUNNING))
        monitored_requests.append(Requests.get_reschedules())
        monitored_requests = []

        for request in monitored_requests:
            if request.status == LocalStatus.APPROVED:
                request.status = LocalStatus.SUBMITTING
                request.submit()  # JUST THE SUBMIT TO GO.
            request.monitor()
            try:
                request.update()
            except SQLAlchemyError as err:
                self.logger.exception("Error updating status of request %d: %s",
                                      request.id, err.message)

        with managed_session() as session:
            monitored_requests = session.query(Requests)\
                                        .filter(Requests.status.in_((LocalStatus.APPROVED,
                                                                     LocalStatus.SUBMITTED,
                                                                     LocalStatus.RUNNING)))\
                                        .all()
            reschedule_requests = session.query(Requests)\
                                         .filter_by(status=LocalStatus.FAILED)\
                                         .join(Requests.parametric_jobs)\
                                         .filter_by(reschedule=True)\
                                         .all()
            monitored_requests.extend(reschedule_requests)

            for request in monitored_requests:
                if request.status == LocalStatus.APPROVED:
                    request.status = LocalStatus.SUBMITTING
                    session.commit()
                    request.submit()
                    session.commit()
                request.update_status()
                session.commit()
