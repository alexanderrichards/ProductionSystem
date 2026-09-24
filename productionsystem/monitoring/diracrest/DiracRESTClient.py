"""
HTTP clients for the DIRAC environment API.
"""
from __future__ import annotations

import logging
from typing import Generator
from contextlib import contextmanager

import httpx

from productionsystem.config import getConfig

DEFAULT_API_URL = "http://dirac-daemon:18861"
REQUEST_TIMEOUT = 600
# _configured_api_url = None
logger = logging.getLogger(__name__)


# def configure_api_url(url):
#     """Set the default DIRAC API URL for this process."""
#     global _configured_api_url  # pylint: disable=global-statement
#     _configured_api_url = url.rstrip("/")


# def _api_url(url=None):
#     if url is not None:
#         return url.rstrip("/")
#     if _configured_api_url is not None:
#         return _configured_api_url
#     return getConfig("monitoring").get("dirac_api_url", DEFAULT_API_URL).rstrip("/")


def _json_value(value):
    """
    Convert nested container values to JSON-compatible structures.
    
    Returns:
        object: JSON-compatible value with mappings, sequences, and set items converted recursively.
    """
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    return value


class DiracAPIJob:
    """
    Record DIRAC Job method calls for execution by the DIRAC daemon.
    """
    def __init__(self):
        """
        Initialize an empty collection of recorded DIRAC method calls.
       
        """
        self.calls = []

    def __getattr__(self, method):
        """
        Create a recorder for an arbitrary public DIRAC job method.

        Args:
            method (str): Name of the method being requested.

        Returns:
            callable: A function that records the method invocation.

        Raises:
            AttributeError: If a private attribute is requested.
        """
        if method.startswith("_"):
            raise AttributeError(method)

        def record_call(*args, **kwargs):
            """
            Record a DIRAC method name and its supplied arguments.
            
            Args:
                *args: Positional arguments to record for the DIRAC method call.
                **kwargs: Keyword arguments to record for the DIRAC method call.

            Returns:
                None. Appends the recorded call to ``self.calls``.
            """
            self.calls.append({
                "method": method,
                "args": _json_value(args),
                "kwargs": _json_value(kwargs),
            })
            return None

        return record_call

    def as_payload(self):
        """
        Return the JSON representation consumed by the REST API.

        Returns:
            dict: Payload containing the recorded DIRAC job method calls.
        """
        return {"calls": self.calls}


type DiracAPIJobClass = type[DiracAPIJob]


class _RESTClient:
    """
    Shared HTTP transport for DIRAC REST clients.
   
    """
    def __init__(self):
        """
        Initialize the HTTP client using the configured DIRAC API URL.
       
        """
        self.api_url = getConfig("monitoring").get("dirac_api_url", "").rstrip("/")
        if not self.api_url:
            logger.warning("DIRAC API URL not configured, using default: %s", DEFAULT_API_URL)
            self.api_url = DEFAULT_API_URL
        self.session = httpx.Client()

    def close(self):
        """
        Close the underlying HTTP connection pool.
        """
        self.session.close()

    def _request(self, method, path, payload):
        """
        Send a JSON request to the DIRAC REST service.

        Args:
            method (str): HTTP method.
            path (str): API path relative to the configured base URL.
            payload (object): JSON-serializable request body.

        Returns:
            object: Decoded JSON response.
        """
        response = self.session.request(
            method,
            self.api_url + path,
            json=_json_value(payload),
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()


class DiracAPIClient(_RESTClient):
    """
    Client for DIRAC job resources.
    """
    def activeConnection(self):
        """
        Test the connection to the DIRAC API.

        Returns:
            bool: True when the health endpoint returns ``{"status": "ok"}``.
        """
        response = self._request("GET", "/health", {})
        if not isinstance(response, dict) or response.get("status") != 'ok':
            return False
        return True

    def submitJob(self, job: DiracAPIJob):
        """
        Submit a recorded DIRAC job.

        Args:
            job: Recorded DIRAC job definition to submit.

        Returns:
            dict: Decoded DIRAC submitJob response.
        """
        if not isinstance(job, DiracAPIJob):
            raise TypeError("job must be an instance of DiracAPIJob")
        return self._request("POST", "/jobs", job.as_payload())

    def getJobStatus(self, job_ids: set[int]):
        """
        Return statuses for the supplied DIRAC job IDs.

        Args:
            job_ids: DIRAC job IDs whose statuses should be queried.

        Returns:
            dict: Decoded DIRAC status response with integer job-ID keys when successful.
        """
        result = self._request("POST", "/jobs/status", {"job_ids": list(job_ids)})
        if result.get("OK") and isinstance(result.get("Value"), dict):
            result["Value"] = {int(key): value for key, value in result["Value"].items()}
        return result

    def rescheduleJob(self, job_ids: set[int]):
        """
        Reschedule the supplied DIRAC jobs.

        Args:
            job_ids: DIRAC job IDs to reschedule.

        Returns:
            dict: Decoded DIRAC rescheduleJob response.
        """
        return self._request("POST", "/jobs/reschedule", {"job_ids": list(job_ids)})

    def killJob(self, job_ids: set[int]):
        """
        Kill the supplied DIRAC jobs.

        Args:
            job_ids: DIRAC job IDs to kill.

        Returns:
            dict: Decoded DIRAC killJob response.
        """
        return self._request("POST", "/jobs/kill", {"job_ids": list(job_ids)})

    def deleteJob(self, job_ids: set[int]):
        """
        Delete the supplied DIRAC jobs.

        Args:
            job_ids: DIRAC job IDs to delete.

        Returns:
            dict: Decoded DIRAC deleteJob response.
        """
        return self._request("DELETE", "/jobs", {"job_ids": list(job_ids)})


class DiracCatalogueClient(_RESTClient):
    """
    Client for DIRAC catalogue resources.
    """
    def __init__(self, rpc_endpoint: str):
        """
        Initialize a catalogue client.

        Args:
            rpc_endpoint (str): DIRAC RPC endpoint used for catalogue calls.
        """
        super().__init__()
        self.rpc_endpoint = rpc_endpoint

    def listDirectory(self, *args):
        """
        List a directory through the configured DIRAC RPC endpoint.

        Args:
            *args: Arguments passed to DIRAC ``listDirectory``.

        Returns:
            dict: Decoded DIRAC catalogue directory listing response.
        """
        return self._request(
            "POST",
            "/catalogue/directories",
            {"rpc_endpoint": self.rpc_endpoint, "args": args},
        )


@contextmanager
def dirac_rpc_client(rpc_endpoint: str) -> Generator[DiracCatalogueClient]:
    """
    Yield a DIRAC catalogue REST client.
    """
    client = DiracCatalogueClient(rpc_endpoint)
    try:
        yield client
    finally:
        client.close()


@contextmanager
def dirac_api_client() -> Generator[DiracAPIClient]:
    """
    Yield a DIRAC job REST client.
    """
    client = DiracAPIClient()
    try:
        yield client
    finally:
        client.close()


@contextmanager
def dirac_api_job_client() -> Generator[tuple[DiracAPIClient, DiracAPIJobClass]]:
    """
    Yield a DIRAC job REST client and a job definition class.
    """
    client = DiracAPIClient()
    try:
        yield client, DiracAPIJob
    finally:
        client.close()
