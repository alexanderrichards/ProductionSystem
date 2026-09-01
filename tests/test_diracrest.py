"""Tests for the DIRAC REST transport."""
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from productionsystem.monitoring.diracrest.DiracRESTClient import (
    DiracAPIClient,
    RESTJob,
)
from productionsystem.monitoring.diracrest.DiracRESTServer import create_app


class FakeJob:
    """Minimal DIRAC Job replacement."""

    def __init__(self):
        self.name = None
        self.sandbox = None

    def setName(self, name):
        self.name = name

    def setInputSandbox(self, files):
        self.sandbox = files


class FakeDirac:
    """Minimal DIRAC API replacement."""

    submitted_job = None

    def submitJob(self, job):
        type(self).submitted_job = job
        return {"OK": True, "Value": 42}

    def getJobStatus(self, job_ids):
        return {"OK": True, "Value": {
            job_id: {"Status": "Done"} for job_id in job_ids
        }}

    def rescheduleJob(self, job_ids):
        return {"OK": True, "Value": job_ids}

    def killJob(self, job_ids):
        return {"OK": True, "Value": job_ids}

    def deleteJob(self, job_ids):
        return {"OK": True, "Value": job_ids}


class FakeRPCClient:
    """Minimal DIRAC catalogue client replacement."""

    def __init__(self, endpoint):
        self.endpoint = endpoint

    def listDirectory(self, path, verbose):
        return {"OK": True, "Value": {
            "endpoint": self.endpoint,
            "path": path,
            "verbose": verbose,
        }}


def test_server_exposes_job_and_catalogue_resources():
    """The FastAPI resources execute the corresponding DIRAC operations."""
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
    """Job definitions cannot invoke methods outside the Job API."""
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
    """Lifecycle resources pass integer job IDs to DIRAC."""
    client = TestClient(create_app(FakeJob, FakeDirac, FakeRPCClient))
    response = client.request(method.upper(), path, json={"job_ids": [41, 42]})
    assert response.status_code == 200
    assert response.json() == {"OK": True, "Value": [41, 42]}


def test_client_serializes_jobs_and_restores_integer_status_keys():
    """The HTTP client preserves the data shapes expected by monitoring."""
    client = DiracAPIClient("http://dirac-api")
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "OK": True,
        "Value": {"42": {"Status": "Done"}},
    }
    client.session.request = Mock(return_value=response)

    job = RESTJob()
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
