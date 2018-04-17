"""Monitoring Daemon."""
import logging
import time
from datetime import datetime

import requests
from daemonize import Daemonize
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
        with managed_session() as session:
            session.query(Services)\
                   .filter(Services.name == "monitoringd")\
                   .update({'status': ServiceStatus.DOWN})
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
        with managed_session() as session:
            query = session.query(Services)

            # DIRAC
            query_dirac = query.filter(Services.name == "DIRAC")
            status = ServiceStatus.DOWN
            if requests.get("https://dirac.gridpp.ac.uk/DIRAC/",
                            cert=self.cert, verify=self.verify)\
                       .status_code == 200:
                status = ServiceStatus.UP
            if query_dirac.one_or_none() is None:
                session.add(Services(name='DIRAC', status=status))
            else:
                query_dirac.update({'status': status})

            # monitoringd
            query_monitoringd = query.filter(Services.name == "monitoringd")
            if query_monitoringd.one_or_none() is None:
                session.add(Services(name='monitoringd', status=ServiceStatus.UP))
            else:
                query_monitoringd.update({'status': ServiceStatus.UP})

    def monitor_requests(self):
        """
        Monitor the DB requests.

        Check the status of ongoing DB requests and either update them or
        create new Ganga tasks for new requests.
        """
        with managed_session() as session:
            monitored_requests = session.query(Requests)\
                                        .filter(Requests.status.in_((LocalStatus.APPROVED,
                                                                     LocalStatus.SUBMITTED,
                                                                     LocalStatus.RUNNING)))\
                                        .all()
            reschedule_requests = session.query(Requests)\
                                         .filter_by(status=LocalStatus.FAILED)\
                                         .join(Requests.parametricjobs)\
                                         .filter_by(reschedule=True)\
                                         .all()
            monitored_requests.extend(reschedule_requests)

            for request in monitored_requests:
                if request.status == LocalStatus.APPROVED:
                    request.status = LocalStatus.SUBMITTING
                    session.commit()
                    request.submit()
                request.update_status()
                session.commit()
