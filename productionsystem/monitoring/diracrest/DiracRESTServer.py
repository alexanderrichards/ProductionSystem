"""
FastAPI server for the DIRAC environment.
"""
from __future__ import annotations

import logging
from functools import wraps
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

try:
    # imports from the DIRAC environment. Note: these are not dependencies for the core application so may be missing.
    from DIRAC.Core.DISET.RPCClient import RPCClient  # type: ignore[import-not-found]
    from DIRAC.Interfaces.API.Dirac import Dirac  # type: ignore[import-not-found]
    from DIRAC.Interfaces.API.Job import Job  # type: ignore[import-not-found]
except ImportError as err:
    logger.error("Failed to import DIRAC modules: %s", err)
    raise ImportError("Failed to import DIRAC modules") from err


class FixedJob(Job):
    """
    DIRAC job subclass that exposes the supported priority setter.
   
    """
    def setPriority(self, priority):
        """
        Set the priority on the underlying DIRAC job.

        Args:
            priority (int): Priority value accepted by DIRAC.
        """
        self._setParamValue("Priority", priority)

class JobCall(BaseModel):
    """
    A method call used to construct a DIRAC job.
    """
    method: str
    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)


class JobDefinition(BaseModel):
    """
    A serializable DIRAC job definition.
    """
    calls: list[JobCall] = Field(default_factory=list)


class JobIds(BaseModel):
    """
    A collection of DIRAC job IDs.
    """
    job_ids: list[int]


class DirectoryRequest(BaseModel):
    """
    A request to list a DIRAC catalogue directory.
    """
    rpc_endpoint: str
    args: list[Any] = Field(default_factory=list)


def _exception_handling(api):
    """
    Wrap an endpoint and translate unexpected errors to HTTP 502 responses.
    
    Returns:
        callable: Endpoint wrapper that preserves explicit HTTP errors and converts unexpected failures to 502 responses.
    """
    @wraps(api)
    def wrapped(*args, **kwargs):
        """
        Invoke the endpoint while preserving its HTTP error semantics.
        
        Args:
            *args: Positional arguments passed to the wrapped endpoint.
            **kwargs: Keyword arguments passed to the wrapped endpoint.

        Returns:
            Any: Value returned by the wrapped endpoint.

        Raises:
            HTTPException: Re-raises endpoint HTTP errors or reports unexpected DIRAC failures as 502.
        """
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
    """
    Create the DIRAC environment FastAPI application.

    Returns:
        FastAPI: Application with health, job, and catalogue endpoints registered.
    """
    app = FastAPI(title="ProductionSystem DIRAC API", version="1.0.0")

    @app.get("/health")
    def health():
        """
        Return a health response when the service is available.
        
        Returns:
            dict[str, str]: Health status payload.
        """
        return {"status": "ok"}

    @app.post("/jobs")
    @_exception_handling
    def submit_job(definition: JobDefinition):
        """
        Construct and submit a DIRAC job from recorded method calls.
        
        Returns:
            dict: DIRAC submitJob response.
        """
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
        """
        Return DIRAC status information for the requested job IDs.
        
        Returns:
            dict: DIRAC job status response.
        """
        return Dirac().getJobStatus(request.job_ids)


    @app.post("/jobs/reschedule")
    @_exception_handling
    def reschedule_jobs(request: JobIds):
        """
        Reschedule the requested DIRAC jobs.
        
        Returns:
            dict: DIRAC rescheduleJob response.
        """
        return Dirac().rescheduleJob(request.job_ids)

    @app.post("/jobs/kill")
    @_exception_handling
    def kill_jobs(request: JobIds):
        """
        Kill the requested DIRAC jobs.
        
        Returns:
            dict: DIRAC killJob response.
        """
        return Dirac().killJob(request.job_ids)

    @app.delete("/jobs")
    @_exception_handling
    def delete_jobs(request: JobIds):
        """
        Delete the requested DIRAC jobs.
        
        Returns:
            dict: DIRAC deleteJob response.
        """
        return Dirac().deleteJob(request.job_ids)

    @app.post("/catalogue/directories")
    @_exception_handling
    def list_directory(request: DirectoryRequest):
        """
        List a catalogue directory through the configured RPC endpoint.
        
        Returns:
            dict: DIRAC catalogue listDirectory response.
        """
        return RPCClient(request.rpc_endpoint).listDirectory(*request.args)

    return app
