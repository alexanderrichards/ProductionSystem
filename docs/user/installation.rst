Installation and deployment
===========================

Choose a deployment model
-------------------------

Use an existing managed deployment if you only need to submit requests.
Installation is for operators and developers.

The repository supplies a Python package and Linux-oriented Docker deployment
examples. It does not provision a complete site configuration automatically:
you must arrange database credentials, certificates, DIRAC configuration,
VOMS access, and the workload extension appropriate to your experiment.

Runtime prerequisites
----------------------

* Use Python 3.12 or newer for the main application and Python client. Current
  modules use ``type`` aliases and other modern Python features; the package
  metadata does not currently declare a minimum version.
* Run daemons on Linux or another supported POSIX environment. ``daemonize``
  requires POSIX facilities, even when a daemon is started in foreground mode.
  On Windows, use a Linux container or WSL for the full service stack.
* Install Git for local repository listing and package installs from Git.
* Provide a supported SQLAlchemy database and driver. PyMySQL is included for
  ``mysql+pymysql`` URLs; SQLite is useful for isolated local work.
* Provide a separately configured DIRAC environment and valid credentials.
  DIRAC itself is not installed as a core package dependency.
* Provide Apache with TLS and client-certificate verification for production
  browser/API access.
* If the workload uses CVMFS, mount the required repositories on the web host
  and any other component that needs them.

The Docker DIRAC image currently configures DIRAC 8.0.74 by default. Some DIRAC
environments use Python 3.11; the REST bridge contains compatibility measures,
but this does not make the entire main application Python 3.11-compatible.
Validate your chosen DIRAC distribution and package version together.

Install from a checkout
-----------------------

In a Linux shell, from the repository root:

.. code-block:: bash

   python3.12 -m venv .venv
   . .venv/bin/activate
   python -m pip install -e .
   webapp-daemon.py --help
   monitoring-daemon.py --help
   dirac-daemon.py --help
   userdb-update.py --help

Editable installation is convenient for development. For a managed deployment,
install an explicitly selected release or revision into a dedicated environment
and retain a record of that revision and its dependencies. Install any workload
extension into the same environment before starting services.

The installed script names include the ``.py`` suffix. They are script files,
not ``python -m productionsystem.webapp-daemon`` modules.

An isolated web-only demonstration
-----------------------------------

The web application's mock mode bypasses certificate authentication and creates
a dummy administrator. It does not provide a complete simulated production
backend or a substitute for testing DIRAC integration.

.. warning::

   Web mock startup deletes ``requests.db`` in the current working directory,
   overrides the requested database URL with that SQLite file, and recreates
   it. Use a new, disposable directory. Bind only to loopback and never expose
   mock mode to an untrusted network.

After installation, run from a dedicated empty directory:

.. code-block:: bash

   mkdir -p /tmp/productionsystem-demo
   cd /tmp/productionsystem-demo
   webapp-daemon.py start \
     --mock-mode --debug-mode \
     --socket-host 127.0.0.1 --socket-port 8080 \
     --pid-file /tmp/productionsystem-demo/webapp.pid

Open ``http://127.0.0.1:8080`` on that host. Stop the foreground process with
Ctrl-C. Requests can be created and inspected, but approval will not execute
work without a configured monitoring/DIRAC setup.

Native production service layout
--------------------------------

Create a restricted service account and directories for configuration, PID
files, logs, and data. Keep the configuration file and private keys readable
only by the required account. The web and monitoring processes must use the
same database; the DIRAC service need not run in the same Python environment.

Recommended startup sequence:

#. Make the database reachable and back up any existing data.
#. Install the same workload model extension in processes that read/write
   its mapped tables.
#. Configure DIRAC, certificate trust, and the execution identity/proxy.
#. Synchronize VOMS users against the selected database.
#. Start the DIRAC REST daemon and verify ``/health``.
#. Start monitoring with the matching private DIRAC URL.
#. Start the web server behind the certificate-validating reverse proxy.
#. Establish the first administrator and perform a small approved validation
   request before accepting production work.

Full commands and checks are in :doc:`operations`; use
:doc:`configuration` to create the shared INI file first.

Docker Compose deployment
-------------------------

The supplied Compose stack includes:

.. list-table::
   :header-rows: 1

   * - Service
     - Role
   * - ``mariadb``
     - Persistent production database.
   * - ``dirac-daemon``
     - DIRAC runtime, internal REST service, proxy initialization, and startup
       VOMS synchronization.
   * - ``monitoring-daemon``
     - Periodic service checks, submission, and monitoring.
   * - ``webapp``
     - Internal FastAPI service.
   * - ``apache``
     - Public HTTPS and certificate-authenticating reverse proxy.

Before building, review ``docker/compose.yaml`` and the Dockerfiles. In the
``docker`` directory, create a private, untracked ``.env`` containing values for:

* ``GIT_BRANCH``: selected Git revision/branch used by remote build contexts.
* ``PY_VERSION``: main Python image tag, for example ``3.14.3-alpine3.23``.
* ``MARIADB_DATABASE``, ``MARIADB_USER``, ``MARIADB_PASSWORD``, and
  ``MARIADB_ROOT_PASSWORD``: the intended database and locally chosen secrets.
* ``GLOBUS_CERT`` and ``GLOBUS_KEY``: host paths to client credential files.

The Compose file currently specifies the DIRAC version as a build argument
directly; merely setting ``DIRAC_VERSION`` in ``.env`` does not override that
entry. Inspect the effective configuration locally:

.. code-block:: bash

   cd docker
   docker compose config
   docker compose up --build -d
   docker compose ps
   docker compose logs --tail=100 dirac-daemon monitoring-daemon webapp

``docker compose config`` can print expanded secrets. Do not paste its output
into tickets or shared logs. The base Compose build contexts use the remote
repository, not your working tree. Use an appropriate revision and ensure the
application configuration copied into the images matches the database
environment values. Compose variables do not automatically substitute values
inside the Python INI file.

The checked-in deployment is a starting point, not a hardened site deployment:

* The Apache image uses a generated self-signed host certificate supplied through
  the shared grid-security volume. Replace it with an appropriate server
  certificate and hostname for public use.
* The Compose database port is published to the host. Restrict or remove that
  mapping if it is not required.
* Keep the web server and DIRAC API on private networks; do not publish their
  ports as an authentication shortcut.
* Review restart policy, credential/proxy renewal, image versions, and storage
  permissions for your site.

Persistent storage and shared sandboxes
---------------------------------------

The MariaDB volume holds production data. The grid-security volume provides
trust material and host certificate files. The temporary sandbox volume is
mounted at ``/tmp`` in both monitoring and DIRAC containers.

The sandbox sharing is essential: submission sends filesystem paths, not file
contents. The DIRAC process must see the files at the same absolute paths while
submission is in progress. Preserve that property in any non-Docker deployment
as well.

Stopping Compose without deleting data
--------------------------------------

.. code-block:: bash

   docker compose stop

Do not use volume-removal options such as ``down --volumes`` as routine
shutdown instructions. Those options can destroy the database and other
persistent deployment state.
