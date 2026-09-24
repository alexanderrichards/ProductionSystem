"""
Daembn process hosting the DIRAC FastAPI application.
"""
from __future__ import annotations

import uvicorn
from daemonize import Daemonize

from .DiracRESTServer import create_app


class DiracDaemon(Daemonize):
    """
    DIRAC daemon hosting the FastAPI application.
    """
    def __init__(self, address, **kwargs):
        """
        Initialize the daemon.

        Args:
            address (tuple[str, int]): Host and port on which to serve.
            **kwargs: Additional options passed to ``Daemonize``.
        """
        self._address = address
        super().__init__(action=self.main, **kwargs)

    def exit(self):
        """
        Stop the daemon while suppressing a successful ``SystemExit``.
        
        Returns:
            object | None: Result from ``Daemonize.exit`` unless it exits successfully.
        """
        try:
            return super().exit()
        except SystemExit as err:
            if err.code != 0:
                raise

    def main(self):
        """
        Run the HTTP server.
        """
        host, port = self._address
        self.logger.info(f"Starting DIRAC REST daemon on {host}:{port}")
        uvicorn.run(create_app(), host=host, port=port, log_config=None)
