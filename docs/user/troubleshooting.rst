Troubleshooting and support
===========================

Start with the failing layer
----------------------------

Determine whether failure occurs before TLS connects, during authentication,
when creating a request, during monitoring, or inside an external job.
Record the time, public request ID, parametric-job ID, and DIRAC IDs where
available. Check :doc:`requests` before repeating a creation or removal action.

.. list-table:: Common symptoms
   :header-rows: 1
   :widths: 28 72

   * - Symptom
     - Checks and action
   * - Browser rejects the server certificate
     - Verify hostname, expiry, certificate chain, and client trust roots.
       Correct trust configuration; do not bypass validation.
   * - No client certificate prompt or TLS handshake failure
     - Confirm the certificate/private key are installed in the browser,
       are unexpired, and chain to a CA accepted by Apache.
   * - HTTP 401 from the application
     - The proxy identity headers are incomplete or certificate verification
       is not ``SUCCESS``. Ask the operator to inspect the trusted proxy path.
   * - HTTP 403
     - The identity may be unknown/suspended, or the operation requires an
       administrator. Check the exact response detail and VOMS synchronization.
   * - Dashboard does not load scripts or dialogs
     - Inspect browser network errors. The default templates load JavaScript
       and CSS from external CDNs; site content policy or offline access can
       prevent them loading.
   * - Submit remains disabled
     - Read the upload status and preview error. Check the first worksheet,
       headers, rows, numeric/boolean types, and extension preparation hook.
   * - HTTP 400 on creation
     - Check the JSON ``request`` wrapper, non-empty object, and accepted
       Pydantic field types. A spreadsheet preview does not replace validation.
   * - HTTP 422
     - FastAPI rejected a path parameter, missing form field, or request shape
       before the handler ran. Inspect the response's validation details.
   * - HTTP 409 on status change
     - The request is not in an allowed source state for approval/check/close.
       Reload it instead of blindly retrying.
   * - HTTP 404 for a request or job
     - Verify the composite IDs and ownership. Owner filtering can make another
       user's resource appear absent.
   * - HTTP 500
     - Inspect backend logs for database, duplicate identity, provider API,
       extension, or serialization errors. Do not assume the request was not
       persisted.
   * - Proxy HTTP 502/503
     - Check backend availability, listener address, service ordering, and
       Uvicorn concurrency limits.

Requests do not progress
------------------------

``Requested``
   An administrator has not approved the request. Monitoring does not submit
   ordinary requested work.

``Approved`` for longer than expected
   Check monitoring process state, database URL consistency, service timestamp,
   DIRAC API connectivity, and the polling interval.

``Submitting`` or unexpected ``Unknown``
   Check request/group logs and monitoring tracebacks. Confirm that the
   extension generates jobs, that sandbox paths are visible to the DIRAC
   process, and that external submission returned job IDs.

``Failed`` with no automatic retry
   Check whether jobs are failed/stalled, whether retry counts are exhausted,
   and whether at least one sibling is ``DONE``. Automatic retry is not an
   unconditional timer; see :doc:`operations`.

``Removing`` persists
   Monitoring must run against the same database to delete the local records.
   Before recovering or forcing cleanup, preserve the external job IDs and
   assess whether they are still active in DIRAC.

Status appears stale
   Browser refresh and backend monitoring are separate intervals. Also check
   whether the last pass failed or is blocked on an external operation. A
   recorded service heartbeat is not proof that every request was processed.

DIRAC service does not start or connect
---------------------------------------

On a native deployment, explicitly configure ``dirac.api_host`` and
``monitoring.dirac_api_url``. The default hostname ``dirac-daemon`` is intended
for a resolvable service environment; it is not automatically a local host
alias. The current monitoring CLI does not accept ``--dirac-api-url``.

Verify the configured runtime is sourced and that DIRAC modules import.
Test the private health endpoint from the monitoring host, then inspect proxy
validity and DIRAC configuration separately. HTTP 502 from the internal API
means its endpoint wrapper caught a DIRAC-side exception; a DIRAC result with
``"OK": false`` is a different failure layer and may still arrive over HTTP 200.

Container startup can stop before the API binds if proxy initialization or
the startup user synchronization fails. Read ``dirac-daemon`` logs rather than
repeatedly restarting dependent services.

Database and import problems
----------------------------

* Confirm that all writers use the same absolute database location or server
  URL. Relative SQLite URLs are resolved against each process working directory.
* Quote INI strings and use Python booleans. Check for unescaped percent signs
  in interpolated values.
* Confirm that the package is installed, not merely placed on ``PYTHONPATH``:
  entry-point metadata is part of application startup.
* Initialize configuration and entry-point discovery before importing lazy SQL
  models in custom scripts. See :doc:`../developer/data-model`.
* A schema mismatch after upgrading is not repaired by ``create_all``.
  Restore a tested schema/application pair or apply a reviewed migration.
* Treat SQLite lock errors under multiple writers as a deployment-capacity
  issue to investigate; do not delete a live database or its journal files.

Collecting a useful support report
----------------------------------

Include:

#. Application revision, extension versions, and deployment method.
#. The failing action and a minimal input shape, without confidential payloads.
#. Time and timezone, request/group/external IDs, and current states.
#. HTTP status and sanitized response detail.
#. Relevant browser errors and sanitized process tracebacks.
#. Whether the failure reproduces with a disposable database or controlled
   validation request.

Never attach private keys, passwords, tokens, full unredacted configuration,
or an unsanitized Compose expansion. Do not delete production requests merely
to make an error disappear; local deletion can discard the tracking needed to
recover external work.
