Operating the service
=====================

Startup and connectivity checks
--------------------------------

Use explicit configuration and PID paths. The following commands assume the
example directories in :doc:`configuration` already exist and are owned by
the service account.

In the configured DIRAC environment:

.. code-block:: bash

   dirac-daemon.py start \
     --config /srv/productionsystem/productionsystem.conf \
     --api-host 127.0.0.1 --api-port 18861

The DIRAC runtime needs its own proxy and GridPP/site configuration before this
command starts. The native script parses DIRAC's command line but does not
perform the Docker entrypoint's proxy initialization or VOMS synchronization.

Check from the monitoring host:

.. code-block:: bash

   curl --fail-with-body http://127.0.0.1:18861/health

The expected JSON is ``{"status":"ok"}``. This endpoint demonstrates that the
REST service is responding; it does not validate the execution proxy or submit
a test job. The internal API's ``/docs`` endpoint provides its generated schema
and should remain private.

In the main application environment:

.. code-block:: bash

   userdb-update.py --config /srv/productionsystem/productionsystem.conf
   monitoring-daemon.py start --config /srv/productionsystem/productionsystem.conf
   webapp-daemon.py start --config /srv/productionsystem/productionsystem.conf

Start Apache only after verifying the backend listener and certificate/trust
configuration. Test both a registered ordinary identity and an administrator
identity. A healthy root page with a dummy user is not a valid production
authentication test.

For container supervision, keep ``--debug-mode`` so the daemon remains in the
foreground. In the base Compose stack the DIRAC entrypoint initializes the
``gridpp_user`` proxy and runs ``userdb-update.py`` before starting the server.
An empty or failed membership synchronization can therefore prevent that
container from reaching its health check.

First administrator
--------------------

New VOMS identities are created with ``admin=False``. There is no unauthenticated
administration endpoint or first-user automatic promotion.

After a successful synchronization, an authorized operator can promote a known
identity from a trusted Python process on the service host. Use the same
environment, configuration, and installed model extensions as the web service:

.. code-block:: python

   from sqlalchemy import select

   from productionsystem.cli import load_entry_points
   from productionsystem.config import ConfigSystem

   config = ConfigSystem.setup("/srv/productionsystem/productionsystem.conf")
   config.entry_point_map = load_entry_points()[0]

   from productionsystem.sql.models import Users
   from productionsystem.sql.registry import SessionRegistry, managed_session

   SessionRegistry.setup(config.get_section("webapp")["dburl"])
   with managed_session() as session:
       user = session.scalars(
           select(Users).where(
               Users.dn == "/C=EXAMPLE/O=Example/CN=Approved Operator",
               Users.ca == "/C=EXAMPLE/O=Example/CN=Example CA",
           )
       ).one()
       if user.suspended:
           raise RuntimeError("Do not grant access to a suspended identity")
       user.admin = True

Replace both identity strings with a verified local record. ``one()`` deliberately
fails if the selection is missing or ambiguous. Do not insert guessed identities
or turn off certificate verification to bootstrap administration.
Subsequent changes can use the **Admins** page or the administrator-only user
form endpoint. Maintain an approved recovery procedure to avoid losing all
administrator access.

VOMS synchronization
---------------------

Run ``userdb-update.py`` on an operator-chosen schedule and inspect its exit
status and logs. There is no built-in recurring scheduler for this command.
It fetches membership information and valid grid-map identities from the VOMS
SOAP services using the configured client credentials.

The reconciliation rules are:

* New DN/CA pairs are inserted as non-administrators.
* Existing pairs retain their local administrator flag; email and suspension
  are updated from the VOMS snapshot.
* Identities absent from VOMS are suspended if they own request, parametric-job,
  or DIRAC-job history. Unreferenced absent identities can be deleted.
* A changed CA is a different identity, not an in-place account rename.
* Empty membership or grid-map snapshots abort with an error before database
  changes. Treat this as a synchronization failure to investigate, not as
  evidence that every account should be removed.

VOMS membership and administrator status are different responsibilities.
Restoring a user's membership may clear suspension on a later successful
synchronization; do not overwrite administrator flags as part of membership
repair.

Certificates, proxy renewal, and trust
---------------------------------------

Track server and client certificate expiry, CA trust updates, and DIRAC proxy
lifetime separately. The Docker entrypoint initializes a proxy at startup,
but the repository does not supply a continuous renewal service.
Arrange renewal using your site's supported credential tooling and verify the
result in the DIRAC environment.

The public Apache service must require client certificates and set the
``SSL-CLIENT-S-DN``, ``SSL-CLIENT-I-DN``, and ``SSL-CLIENT-VERIFY`` headers itself.
Prevent direct access to the backend from untrusted clients, since the
application relies on that trusted-proxy boundary.

The internal DIRAC API has no application-level authentication in the built-in
server. Keep it on a trusted private network or place appropriate authenticated
transport controls in front of it. Never publish it as a general user API.

Monitoring, retries, and health indicators
-------------------------------------------

On each pass the monitor updates service records and processes approved,
submitting, submitted, running, and removing requests. Failed requests with
pending reschedules can also be selected.

Automatic rescheduling considers failed or stalled DIRAC jobs whose retry
count is below ``parametricjobs.reschedules``. It only selects that automatic
retry set when at least one other job in the group is already ``DONE``.
Successful reschedules increment the stored counter. Manual rescheduling
selects failed/stalled jobs without that automatic retry-count condition.

A dashboard badge is based on recorded data. If the monitor is not recorded as
up, the dashboard suppresses the DIRAC badge's stored status. A monitoring
timestamp older than 30 minutes is treated as stale for display. Large pass
durations or a long configured frequency can therefore look like a stalled
service even if the process exists.

Use these checks together:

#. Process/container state and restart count.
#. DIRAC REST ``/health`` from the monitoring host.
#. Database connectivity from web and monitoring environments.
#. Freshness of the ``monitoringd`` service timestamp.
#. Logs for submission/status errors and failed transactions.
#. Actual external job state and expected output in DIRAC.

Logging
--------

Background daemons use ``APP_NAME.log`` in the selected log directory, rotating
at midnight with five backups. Foreground/debug mode uses stream logging.
Use ``-v`` for INFO and ``-vv`` for DEBUG when diagnosing a problem, subject to
the secret-logging warning in :doc:`configuration`.

Request and parametric-job logs are persisted client-visible summaries. They
are not a replacement for process tracebacks, database logs, or external job
stdout/stderr. Capture all relevant layers for a failed production request.

Shutdown, upgrades, and recovery
--------------------------------

Stop monitoring before taking down its dependencies, then stop the web service
and DIRAC daemon as appropriate:

.. code-block:: bash

   monitoring-daemon.py stop --config /srv/productionsystem/productionsystem.conf \
     --pid-file /srv/productionsystem/run/monitoring.pid
   webapp-daemon.py stop --config /srv/productionsystem/productionsystem.conf \
     --pid-file /srv/productionsystem/run/webapp.pid
   dirac-daemon.py stop --config /srv/productionsystem/productionsystem.conf \
     --pid-file /srv/productionsystem/run/dirac.pid

The stop helper uses the selected PID file; it does not infer all daemon
start settings from the corresponding start section. Check process identity
before acting on a stale PID file.

For an upgrade:

#. Announce the maintenance window and stop monitoring and writers.
#. Back up the database with the database vendor's supported tools. For SQLite,
   use its backup facility or make a consistent copy with writers stopped.
#. Preserve configuration, extension versions, image versions, and job IDs.
#. Apply any explicitly reviewed schema migration procedure.
#. Install compatible application and extension versions in all environments.
#. Restart dependencies, then monitoring and web access.
#. Validate authentication, request listing, and a controlled job workflow.

``metadata.create_all`` creates missing tables but is not a schema migration
system. There is no included migration/rollback framework. Test schema changes
and restoration against copies before modifying production data.

Stopping the service does not inherently cancel already submitted external
jobs. After an interrupted submission, reconcile DIRAC job IDs before approving
or recreating work: an external side effect may have succeeded even if a local
database update failed.
