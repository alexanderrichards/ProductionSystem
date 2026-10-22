"""
Tests for the DIRAC REST transport.

Use fake job, API, and catalogue implementations to check endpoint forwarding,
job recording, JSON conversion, and restoration of integer status keys.
"""
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from productionsystem.monitoring.diracrest.DiracRESTClient import (
    DiracAPIClient,
    DiracAPIJob,
)
from productionsystem.monitoring.diracrest.DiracRESTServer import create_app


class FakeJob:
    """
    Minimal DIRAC Job replacement.

    Attributes:
        name (str | None): Most recently assigned job name.
        sandbox (list[str] | None): Most recently assigned input sandbox.
    """
    def __init__(self):
        """
        Initialize a fake job with empty test state.

        Leave the name and sandbox unset until the recorded configuration calls
        are replayed by the endpoint under test.
        """
        self.name = None
        self.sandbox = None

    def setName(self, name):
        """
        Record the job name supplied by the API.

        Args:
            name (str): Job name to retain for assertions.
        """
        self.name = name

    def setInputSandbox(self, files):
        """
        Record the input sandbox supplied by the API.

        Args:
            files (list[str]): Input paths to retain for assertions.
        """
        self.sandbox = files


class FakeDirac:
    """
    Minimal DIRAC API replacement.

    Return deterministic DIRAC-style result envelopes for endpoint assertions.
    Keep the most recently submitted job as shared class state.

    Attributes:
        submitted_job (FakeJob | None): Last job accepted by ``submitJob``.
    """
    submitted_job = None

    def submitJob(self, job):
        """
        Record and accept a submitted fake job.

        Args:
            job (FakeJob): Configured job to retain for assertions.

        Returns:
            dict: Successful DIRAC result with the fixed job identifier 42.
        """
        type(self).submitted_job = job
        return {"OK": True, "Value": 42}

    def getJobStatus(self, job_ids):
        """
        Return a successful status response for each requested job.

        Args:
            job_ids (list[int]): Job identifiers whose statuses are requested.

        Returns:
            dict: Successful DIRAC result mapping each identifier to ``Done``.
        """
        return {"OK": True, "Value": {
            job_id: {"Status": "Done"} for job_id in job_ids
        }}

    def rescheduleJob(self, job_ids):
        """
        Return a successful rescheduling response.

        Args:
            job_ids (list[int]): Identifiers passed by the rescheduling endpoint.

        Returns:
            dict: Successful DIRAC result containing the unchanged identifiers.
        """
        return {"OK": True, "Value": job_ids}

    def killJob(self, job_ids):
        """
        Return a successful kill response.

        Args:
            job_ids (list[int]): Identifiers passed by the kill endpoint.

        Returns:
            dict: Successful DIRAC result containing the unchanged identifiers.
        """
        return {"OK": True, "Value": job_ids}

    def deleteJob(self, job_ids):
        """
        Return a successful deletion response.

        Args:
            job_ids (list[int]): Identifiers passed by the deletion endpoint.

        Returns:
            dict: Successful DIRAC result containing the unchanged identifiers.
        """
        return {"OK": True, "Value": job_ids}


class FakeRPCClient:
    """
    Minimal DIRAC catalogue client replacement.

    Retain the chosen endpoint and echo directory request arguments in a
    DIRAC-style result rather than contacting a catalogue.

    Attributes:
        endpoint (str): RPC service selected by the caller.
    """
    def __init__(self, endpoint):
        """
        Initialize the fake catalogue client.

        Args:
            endpoint (str): RPC service name to retain for assertions.
        """
        self.endpoint = endpoint

    def listDirectory(self, path, verbose):
        """
        Return the supplied directory arguments for assertions.

        Args:
            path (str): Directory path requested by the caller.
            verbose (bool): Verbosity flag supplied by the caller.

        Returns:
            dict: Successful DIRAC result with endpoint, path, and verbosity.
        """
        return {"OK": True, "Value": {
            "endpoint": self.endpoint,
            "path": path,
            "verbose": verbose,
        }}


def test_server_exposes_job_and_catalogue_resources():
    """
    The FastAPI resources execute the corresponding DIRAC operations.

    Check job configuration replay, status response encoding, and catalogue
    argument forwarding through an in-process HTTP test client.
    """
    client = TestClient(create_app(FakeJob, FakeDirac, FakeRPCClient))

    response = client.post("/jobs", json={"calls": [
        {"method": "setName", "args": ["job-name"]},
        {"method": "setInputSandbox", "args": [["input.txt"]]},
    ]})
    assert response.status_code == 200
    assert response.json() == {"OK": True, "Value": 42}
    assert FakeDirac.submitted_job.name == "job-name"
    assert FakeDirac.submitted_job.sandbox == ["input.txt"]

    response = client.post("/jobs/status", json={"job_ids": [42]})
    assert response.json() == {"OK": True, "Value": {"42": {"Status": "Done"}}}

    response = client.post("/catalogue/directories", json={
        "rpc_endpoint": "DataManagement/FileCatalog",
        "args": ["/data", False],
    })
    assert response.json()["Value"] == {
        "endpoint": "DataManagement/FileCatalog",
        "path": "/data",
        "verbose": False,
    }


def test_server_rejects_unknown_job_methods():
    """
    Job definitions cannot invoke methods outside the Job API.

    Submit a private method name and check that the server rejects the
    definition with HTTP 400 rather than executing it.
    """
    client = TestClient(create_app(FakeJob, FakeDirac, FakeRPCClient))
    response = client.post("/jobs", json={"calls": [{"method": "_private"}]})
    assert response.status_code == 400


@pytest.mark.parametrize(
    ("method", "path"),
    (
        ("post", "/jobs/reschedule"),
        ("post", "/jobs/kill"),
        ("delete", "/jobs"),
    ),
)
def test_server_exposes_job_lifecycle_resources(method, path):
    """
    Lifecycle resources pass integer job IDs to DIRAC.

    Args:
        method (str): Parametrized HTTP method for the lifecycle operation.
        path (str): Corresponding rescheduling, kill, or deletion endpoint.
    """
    client = TestClient(create_app(FakeJob, FakeDirac, FakeRPCClient))
    response = client.request(method.upper(), path, json={"job_ids": [41, 42]})
    assert response.status_code == 200
    assert response.json() == {"OK": True, "Value": [41, 42]}


def test_client_serializes_jobs_and_restores_integer_status_keys():
    """
    The HTTP client preserves the data shapes expected by monitoring.

    Inspect mocked outgoing JSON for recorded job calls, then check that
    successful status responses restore integer job identifiers.
    """
    client = DiracAPIClient("http://dirac-api")
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "OK": True,
        "Value": {"42": {"Status": "Done"}},
    }
    client.session.request = Mock(return_value=response)

    job = DiracAPIJob()
    job.setName("job-name")
    job.setInputSandbox(("first", "second"))
    client.submitJob(job)

    _, url = client.session.request.call_args.args
    assert url == "http://dirac-api/jobs"
    assert client.session.request.call_args.kwargs["json"] == {"calls": [
        {"method": "setName", "args": ["job-name"], "kwargs": {}},
        {"method": "setInputSandbox", "args": [["first", "second"]], "kwargs": {}},
    ]}

    assert client.getJobStatus({42})["Value"] == {42: {"Status": "Done"}}
