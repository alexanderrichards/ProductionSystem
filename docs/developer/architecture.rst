Architecture and execution flow
===============================

Process boundaries
-------------------

.. code-block:: text

   Browser / JSI / HTTPS automation
                 |
          Apache + client TLS
                 |
          FastAPI web application ---- SQL database
                                           |
                                    monitoring daemon
                                           |
                                    private HTTP API
                                           |
                                    DIRAC environment
                                           |
                                      external jobs

The web application owns interactive request creation and review. Monitoring
owns asynchronous submission and status refresh. The DIRAC process bridges
those operations into the separately installed DIRAC runtime. Database records
are the coordination mechanism between web and monitoring; there is no included
message broker or task queue.

The web service and monitoring daemon are separate processes with independent
configuration and SQLAlchemy sessions. Do not rely on in-memory state shared
between them. The configuration and session registries are process-local
singletons, not distributed registries.

Source map
-----------

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Location
     - Responsibility
   * - ``productionsystem/cli.py``
     - Entry-point discovery, option precedence, logging, and PID-based stop.
   * - ``productionsystem/config.py`` / ``singleton.py``
     - Literal-valued INI sections and explicit singleton lifecycle.
   * - ``productionsystem/apache_utils.py``
     - Verified certificate identity, local user lookup, and admin dependencies.
   * - ``productionsystem/sql/``
     - Declarative mapping, sessions, status enums, schemas, and workflow models.
   * - ``productionsystem/monitoring/``
     - Periodic checks and the DIRAC REST bridge.
   * - ``productionsystem/webapp/services/``
     - HTML, public REST resources, and Git/CVMFS listings.
   * - ``productionsystem/webapp/templates/`` / ``static_resources/``
     - Jinja2 pages and browser-side interaction.
   * - ``productionsystem/api.py`` / ``http_utils.py`` / ``suds_utils.py``
     - Public Python client, TLS contexts, and VOMS SOAP transport.
   * - ``scripts/``
     - Installed lifecycle and user-synchronization commands.
   * - ``docker/``
     - Example multi-process deployment and development bind mounts.

Application startup
--------------------

Command scripts parse Typer options, read the selected configuration, discover
installed entry points, and configure logging before loading their daemon
classes. This ordering is important: model and web-service imports can resolve
extension entry points immediately.

The web daemon initializes the session registry, assembles service routers,
and mounts packaged static resources last as a fallback. Registered routes
must remain ahead of the root static mount. The ``thread_pool`` option is
passed as Uvicorn's concurrency limit, not a thread-pool size.

The monitor checks DIRAC REST connectivity during construction and initializes
its database registry when its main action starts. The DIRAC daemon constructs
its own FastAPI application in the DIRAC environment. Merely importing a daemon
class does not start its loop; starting the command is a separate lifecycle
operation.

Request creation
------------------

#. The new-request page parses the first spreadsheet worksheet in the browser.
#. A synchronous template hook converts form fields and row objects into a
   request payload. The UI previews a frozen wire-format snapshot.
#. The browser sends ``{"request": ...}`` as JSON to ``POST /api/requests``.
#. FastAPI resolves the verified user. The handler validates the body with
   ``RequestCreate``.
#. ``Requests.create`` constructs parametric jobs numbered from 1 within the
   request and persists them in a managed transaction.
#. The handler returns HTTP 200 with no resource object; the UI reloads the list.

Client-side preview is a usability feature, not a trust boundary. Extensions
must validate accepted fields on the server. A network timeout after the
commit can leave a successfully created request even though the browser reports
a failure.

Approval and monitoring
------------------------

An administrator sets a requested request to ``Approved`` using a form PUT.
On a later pass, monitoring marks it submitting, persists the transition,
calls request submission, and persists the resulting state.
Each parametric job generates recorded DIRAC calls and creates temporary
sandbox files. The private API replays the calls on a real DIRAC job, submits
it, and returns external IDs. Subsequent monitoring queries external states,
updates child records/counters, and reduces them into group and request states.

There is no transaction spanning external submission and SQL persistence.
For example, a submission may succeed and the next database update may fail.
Do not add unconditional retries around that sequence without a reconciliation
or idempotency design.

The loop is synchronous. Submission, HTTP timeouts, health checks, and request
processing all contribute to pass duration. Running multiple independent
monitors against the same database is not established as safe: there is no
included distributed claim/lease mechanism preventing duplicate submission.

Authentication boundaries
--------------------------

The public service trusts Apache to verify a client certificate and overwrite
the certificate identity headers. Application dependencies then resolve an
unsuspended DN/CA record and enforce administrative access where required.
Non-admin resource queries add requester filters.

The private DIRAC API is a separate trust boundary. Its built-in handlers do
not authenticate callers and accept executable job configuration operations.
Network isolation or an appropriately authenticated transport is a deployment
requirement, not an optional property of the public login.

Mock mode replaces the verified-user dependency with a database-backed dummy
identity. It must remain a local development feature. Tests should override
dependencies explicitly rather than introducing production authentication
shortcuts.

Error and serialization layers
-------------------------------

The public REST services translate selected database/validation failures using
``http_error_handle`` and explicit HTTP exceptions. FastAPI performs additional
request validation and Pydantic response serialization.

The private DIRAC wrapper preserves explicit HTTP errors and turns unexpected
exceptions into HTTP 502 with logged context. A successful HTTP response may
still contain a DIRAC ``OK=False`` envelope. Callers must distinguish transport
success from backend operation success.

Pydantic response schemas and ``JSONTableEncoder`` are different serialization
paths. Changes to status names, nested relationships, or timestamps need tests
for both if both remain supported.
