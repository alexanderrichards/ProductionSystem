DIRAC REST integration
======================

Why a separate service exists
-----------------------------

The main application and the DIRAC environment can have different dependency
and Python-version requirements. The REST bridge keeps DIRAC imports and actual
job execution APIs in the DIRAC process. Monitoring needs HTTPX and the local
recording client, not the full DIRAC installation.

``DiracRESTClient`` contains the shared transport, job recorder, catalogue
client, and context managers. ``DiracRESTServer`` imports DIRAC and creates
the FastAPI routes. ``DiracRESTDaemon`` runs that application with Uvicorn.

Configuration and transport
---------------------------

Clients read ``monitoring.dirac_api_url``, remove a trailing slash, and use
``http://dirac-daemon:18861`` with a warning when it is absent.
The transport uses an HTTPX client and supplies a 600-second request timeout.
It recursively converts dictionaries to string-keyed mappings and tuples/sets
to lists. Set iteration order is not a serialization guarantee.

The context managers close the pool even when the context body raises:

.. code-block:: python

   from productionsystem.cli import load_entry_points
   from productionsystem.config import ConfigSystem

   config = ConfigSystem.setup("/srv/productionsystem/productionsystem.conf")
   config.entry_point_map = load_entry_points()[0]

   from productionsystem.monitoring.diracrest.DiracRESTClient import (
       dirac_api_client,
   )

   with dirac_api_client() as client:
       if not client.activeConnection():
           raise RuntimeError("DIRAC REST health check failed")
       result = client.getJobStatus({12345})
       if not result.get("OK"):
           raise RuntimeError(f"DIRAC status operation failed: {result}")
       print(result["Value"])

Use an actual known external ID for diagnostics. The health check only checks
the health response shape. It is not an authentication, proxy, or execution
capability probe.

Recorded job definitions
-------------------------

``DiracAPIJob`` dynamically records public method calls:

.. code-block:: python

   from productionsystem.monitoring.diracrest.DiracRESTClient import DiracAPIJob

   job = DiracAPIJob()
   job.setName("Validation")
   job.setInputSandbox(["/shared/tmp/runscript.sh"])
   payload = job.as_payload()

The payload has this shape:

.. code-block:: json

   {
     "calls": [
       {"method": "setName", "args": ["Validation"], "kwargs": {}},
       {
         "method": "setInputSandbox",
         "args": [["/shared/tmp/runscript.sh"]],
         "kwargs": {}
       }
     ]
   }

No job is created remotely until submission. The server creates a ``FixedJob``,
rejects private names and unknown/non-callable attributes, replays calls in
order, and submits through ``Dirac().submitJob``.
``FixedJob`` supplies ``setPriority`` through DIRAC's parameter helper.

The server performs method existence checks, not a universal compatibility
translation layer. A method supported by one installed DIRAC release may
fail on another. Record only operations verified for the target environment.

Internal resource contract
---------------------------

.. list-table::
   :header-rows: 1
   :widths: 12 32 56

   * - Method
     - Path
     - Request / result
   * - GET
     - ``/health``
     - No meaningful body required; returns ``{"status":"ok"}``.
   * - POST
     - ``/jobs``
     - ``JobDefinition`` with ordered ``calls``; returns DIRAC submission result.
   * - POST
     - ``/jobs/status``
     - ``{"job_ids":[...]}``; returns DIRAC status result.
   * - POST
     - ``/jobs/reschedule``
     - ``{"job_ids":[...]}``; returns DIRAC rescheduling result.
   * - POST
     - ``/jobs/kill``
     - ``{"job_ids":[...]}``; returns DIRAC kill result.
   * - DELETE
     - ``/jobs``
     - JSON body ``{"job_ids":[...]}``; returns DIRAC deletion result.
   * - POST
     - ``/catalogue/directories``
     - ``{"rpc_endpoint":"...", "args":[...]}``; calls RPC ``listDirectory``.

Unlike some public REST conventions, the DELETE job operation has a JSON
body. The client and server must preserve it. Do not replace it with query
parameters on one side only.

DIRAC responses usually use an ``OK`` boolean and either ``Value`` or
``Message``. HTTP status is checked first by the client, then operation success
must be checked by the caller. ``getJobStatus`` restores integer keys in a
successful ``Value`` mapping because JSON object keys are strings.

Unexpected server exceptions become HTTP 502 and are logged with the endpoint
name. Explicit HTTP errors remain unchanged. Invalid public job method names
produce HTTP 400; invalid Pydantic request shapes can produce HTTP 422.

Sandbox lifetime
-----------------

The temporary-resource manager coordinates cleanup after submission.
The generated script and auxiliary input files must exist when DIRAC reads
their paths. The bridge does not upload arbitrary files as REST request bodies.
For separate hosts or containers, mount shared storage at identical absolute
paths and verify both visibility and permissions.

An exception can trigger local cleanup after an external side effect has
already happened. Preserve external IDs in reconciliation workflows and do
not assume a transport timeout means submission did not occur.

Operational boundaries and testing
-----------------------------------

The built-in API does not authenticate requests. Restrict access to trusted
components; do not reuse public browser credentials or proxy headers as an
implicit private-API authentication scheme.

Unit-test the recorder payload, method dispatch, JSON conversion, timeout
settings, error translation, and integer status-key restoration separately.
Server tests need a DIRAC-aware environment or correctly installed import
stubs before importing ``DiracRESTServer``. The current ``create_app`` function
takes no injected backend arguments; tests written against older injected
factory signatures need updating before they can describe the current code.
See :doc:`testing`.
