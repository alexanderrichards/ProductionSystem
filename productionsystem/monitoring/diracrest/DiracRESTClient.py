"""HTTP clients for the DIRAC environment API."""
from __future__ import annotations

import logging
from contextlib import contextmanager

import requests

from productionsystem.config import getConfig

DEFAULT_API_URL = "http://localhost:18861"
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
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    return value


class RESTJob:
    """Record DIRAC Job method calls for execution by the DIRAC daemon."""

    def __init__(self):
        self.calls = []

    def __getattr__(self, method):
        if method.startswith("_"):
            raise AttributeError(method)

        def record_call(*args, **kwargs):
            self.calls.append({
                "method": method,
                "args": _json_value(args),
                "kwargs": _json_value(kwargs),
            })
            return None

        return record_call

    def as_payload(self):
        """Return the JSON representation consumed by the REST API."""
        return {"calls": self.calls}


class _RESTClient:
    def __init__(self):
        self.api_url = getConfig("monitoring").get("dirac_api_url", "").rstrip("/")
        if not self.api_url:
            logger.warning("DIRAC API URL not configured, using default: %s", DEFAULT_API_URL)
            self.api_url = DEFAULT_API_URL
        self.session = requests.Session()

    def close(self):
        """Close the underlying HTTP connection pool."""
        self.session.close()

    def _request(self, method, path, payload):
        response = self.session.request(
            method,
            self.api_url + path,
            json=_json_value(payload),
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()


class DiracAPIClient(_RESTClient):
    """Client for DIRAC job resources."""

    def activeConnection(self):
        """Test the connection to the DIRAC API."""
        response = self._request("GET", "/health", {})
        if not isinstance(response, dict) or response.get("status") != 'ok':
            return False
        return True

    def submitJob(self, job):
        """Submit a recorded DIRAC job."""
        if not isinstance(job, RESTJob):
            raise TypeError("job must be an instance of RESTJob")
        return self._request("POST", "/jobs", job.as_payload())

    def getJobStatus(self, job_ids):
        """Return statuses for the supplied DIRAC job IDs."""
        result = self._request("POST", "/jobs/status", {"job_ids": list(job_ids)})
        if result.get("OK") and isinstance(result.get("Value"), dict):
            result["Value"] = {int(key): value for key, value in result["Value"].items()}
        return result

    def rescheduleJob(self, job_ids):
        """Reschedule the supplied DIRAC jobs."""
        return self._request("POST", "/jobs/reschedule", {"job_ids": list(job_ids)})

    def killJob(self, job_ids):
        """Kill the supplied DIRAC jobs."""
        return self._request("POST", "/jobs/kill", {"job_ids": list(job_ids)})

    def deleteJob(self, job_ids):
        """Delete the supplied DIRAC jobs."""
        return self._request("DELETE", "/jobs", {"job_ids": list(job_ids)})


class DiracCatalogueClient(_RESTClient):
    """Client for DIRAC catalogue resources."""

    def __init__(self, rpc_endpoint):
        super().__init__()
        self.rpc_endpoint = rpc_endpoint

    def listDirectory(self, *args):
        """List a directory through the configured DIRAC RPC endpoint."""
        return self._request(
            "POST",
            "/catalogue/directories",
            {"rpc_endpoint": self.rpc_endpoint, "args": args},
        )


@contextmanager
def dirac_rpc_client(rpc_endpoint):
    """Yield a DIRAC catalogue REST client."""
    client = DiracCatalogueClient(rpc_endpoint)
    try:
        yield client
    finally:
        client.close()


@contextmanager
def dirac_api_client():
    """Yield a DIRAC job REST client."""
    client = DiracAPIClient()
    try:
        yield client
    finally:
        client.close()


@contextmanager
def dirac_api_job_client():
    """Yield a DIRAC job REST client and a job definition class."""
    client = DiracAPIClient()
    try:
        yield client, RESTJob
    finally:
        client.close()
