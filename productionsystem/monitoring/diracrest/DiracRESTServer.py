"""FastAPI server for the DIRAC environment."""
from __future__ import annotations

import logging
from functools import wraps
from typing import Any, Callable

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

try:
    from DIRAC.Core.DISET.RPCClient import RPCClient
    from DIRAC.Interfaces.API.Dirac import Dirac
    from DIRAC.Interfaces.API.Job import Job
except ImportError as err:
    logger.error("Failed to import DIRAC modules: %s", err)
    raise ImportError("Failed to import DIRAC modules") from err


class FixedJob(Job):
    def setPriority(self, priority):
        self._setParamValue("Priority", priority)

class JobCall(BaseModel):
    """A method call used to construct a DIRAC job."""

    method: str
    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)


class JobDefinition(BaseModel):
    """A serializable DIRAC job definition."""

    calls: list[JobCall] = Field(default_factory=list)


class JobIds(BaseModel):
    """A collection of DIRAC job IDs."""

    job_ids: list[int]


class DirectoryRequest(BaseModel):
    """A request to list a DIRAC catalogue directory."""

    rpc_endpoint: str
    args: list[Any] = Field(default_factory=list)


def _exception_handling(api):
    @wraps(api)
    def wrapped(*args, **kwargs):
        try:
            return api(*args, **kwargs)
        except HTTPException:
            raise
        except Exception as err:
            logger.exception(f"DIRAC API operation {api.__qualname__!r} failed")
            raise HTTPException(status_code=502,
                                detail="DIRAC API operation %r failed: %s" % (api.__qualname__, err)) from err
    return wrapped

def create_app():
    """Create the DIRAC environment FastAPI application."""

    app = FastAPI(title="ProductionSystem DIRAC API", version="1.0.0")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/jobs")
    @_exception_handling
    def submit_job(definition: JobDefinition):
        job = FixedJob()
        for call in definition.calls:
            if call.method.startswith("_"):
                raise HTTPException(status_code=400, detail="Private methods are not allowed")
            target = getattr(job, call.method, None)
            if not callable(target):
                raise HTTPException(status_code=400, detail="Unknown method: %s" % call.method)
            target(*call.args, **call.kwargs)
        return Dirac().submitJob(job)

    @app.post("/jobs/status")
    @_exception_handling
    def get_job_status(request: JobIds):
        return Dirac().getJobStatus(request.job_ids)


    @app.post("/jobs/reschedule")
    @_exception_handling
    def reschedule_jobs(request: JobIds):
        return Dirac().rescheduleJob(request.job_ids)

    @app.post("/jobs/kill")
    @_exception_handling
    def kill_jobs(request: JobIds):
        return Dirac().killJob(request.job_ids)

    @app.delete("/jobs")
    @_exception_handling
    def delete_jobs(request: JobIds):
        return Dirac().deleteJob(request.job_ids)

    @app.post("/catalogue/directories")
    @_exception_handling
    def list_directory(request: DirectoryRequest):
        return RPCClient(request.rpc_endpoint).listDirectory(*request.args)

    return app
