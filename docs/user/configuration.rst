Configuration reference
========================

File location and precedence
----------------------------

All four command-line applications default to
``~/.config/productionsystem/productionsystem.conf``. Supply another file with
``--config`` or ``-c``. A missing file is logged and commands continue with
their defaults, which can accidentally point different processes at different
SQLite databases. Use explicit absolute paths in managed services.

For options present on the selected command:

#. An explicitly supplied CLI value wins.
#. Otherwise, a matching key in that command's INI section overrides the
   command default.
#. Otherwise, the built-in default is used.

Additional sections such as ``parametricjobs`` are read directly by application
code. ``monitoring.dirac_api_url`` is also read directly by the internal REST
client: there is currently no ``--dirac-api-url`` option on the monitoring
command. Set that URL in the file, even if an older example suggests a CLI flag.

INI values are Python literals
------------------------------

Values are parsed with ``ast.literal_eval``, not interpreted as plain strings.
Quote strings, use ``True`` and ``False`` for booleans, and use unquoted integer
values for counts and ports:

.. code-block:: ini

   [monitoring]
   frequency = 5
   verify = True
   dirac_api_url = "http://127.0.0.1:18861"

``frequency = "5"`` is a string, not an integer. ``verify = true`` is not a
valid Python boolean literal. Invalid literal values can fail startup before
the daemon is launched. Section and option names should match the code's
spelling; option-name case is preserved.

ConfigParser interpolation still applies. If an INI value contains a literal
percent sign, escape it as ``%%`` in the file. This matters for percent-encoded
SQLAlchemy URLs and some URL credentials.

Example single-host configuration
----------------------------------

This example assumes the application account can write the data, run, and log
directories and that DIRAC is started in its own configured environment.
Replace the VOMS URL and trust paths as needed:

.. code-block:: ini

   [webapp]
   dburl = "sqlite:////srv/productionsystem/data/requests.db"
   socket_host = "127.0.0.1"
   socket_port = 8080
   thread_pool = 8
   git_schema = "GITHUB"
   git_api_base_url = "https://api.github.com/repos"
   pid_file = "/srv/productionsystem/run/webapp.pid"
   log_dir = "/srv/productionsystem/log"
   verbose = 1

   [monitoring]
   dburl = "sqlite:////srv/productionsystem/data/requests.db"
   dirac_api_url = "http://127.0.0.1:18861"
   frequency = 5
   cert = "/srv/productionsystem/credentials/usercert.pem"
   key = "/srv/productionsystem/credentials/userkey.pem"
   verify = True
   trusted_cas = "/etc/grid-security/certificates"
   pid_file = "/srv/productionsystem/run/monitoring.pid"
   log_dir = "/srv/productionsystem/log"
   verbose = 1

   [dirac]
   api_host = "127.0.0.1"
   api_port = 18861
   pid_file = "/srv/productionsystem/run/dirac.pid"
   log_dir = "/srv/productionsystem/log"
   verbose = 1

   [userdb]
   dburl = "sqlite:////srv/productionsystem/data/requests.db"
   voms = "https://voms.gridpp.ac.uk:8443/voms/lz/services"
   cert = "/srv/productionsystem/credentials/usercert.pem"
   key = "/srv/productionsystem/credentials/userkey.pem"
   trusted_cas = "/etc/grid-security/certificates"
   verify = True
   verbose = 1

   [parametricjobs]
   reschedules = 2

SQLite URLs use four slashes for an absolute Unix path.
``sqlite:///requests.db`` is relative to the process working directory.
For a shared database server use, for example, the SQLAlchemy URL form
``mysql+pymysql://USER:PASSWORD@HOST/DATABASE`` with locally supplied credentials.
Protect that file and URL-encode special characters in credentials.

Common command options
-----------------------

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Option/key
     - Behavior
   * - ``--config`` / ``config``
     - Select the INI file. Select it on the CLI rather than attempting to
       redirect loading through a key inside another INI file.
   * - ``--verbose`` / ``verbose``
     - Repeat ``-v`` on the CLI. Zero gives WARNING, one INFO, and two or more
       DEBUG in the shared logging setup.
   * - ``--pid-file`` / ``pid_file``
     - Daemon PID file. Default is based on the startup working directory.
       Use the same explicit file when stopping.
   * - ``--log-dir`` / ``log_dir``
     - Daemon log directory, defaulting to ``log`` under the startup directory.
   * - ``--debug-mode`` / ``debug_mode``
     - Run in the foreground and log to a stream. It does not itself increase
       log verbosity.
   * - ``--extension`` / ``extension``
     - Validate a discovered extension project name. See
       :doc:`../developer/extensions` for the current discovery semantics.
   * - ``--dburl`` / ``dburl``
     - SQLAlchemy URL for web, monitoring, and user synchronization. Not a
       DIRAC daemon option.

The available options differ between ``start`` and ``stop``.
Use ``COMMAND start --help`` or ``COMMAND stop --help`` for the installed
version rather than passing start-only settings to stop commands.

Web application settings
-------------------------

``socket_host`` / ``socket_port``
   Listener interface and port. Defaults are ``0.0.0.0`` and ``8080``.
   In native production deployments, bind loopback or a private interface behind
   Apache.

``thread_pool``
   Default 8. Despite the historical name, this is currently passed to Uvicorn
   as ``limit_concurrency``; it is not a configured number of worker threads.

``git_schema``
   Case-sensitive enum name: ``GITHUB`` (default), ``GITLAB``, or ``LOCAL``.

``git_api_base_url``
   Provider API base. The GitHub default is ``https://api.github.com/repos``.
   For GitLab, supply the API root ending in ``/api/v4``. For ``LOCAL``, supply
   the directory holding ``owner/repository`` checkouts.

``git_token``
   Optional provider token. GitHub uses an Authorization token header; GitLab
   uses Private-Token. Local repository mode does not need a provider token.

``mock_mode``
   Default False. Enables dummy authentication and a destructive local database
   reset; see the warning in :doc:`installation`.

Monitoring and DIRAC settings
-----------------------------

``frequency``
   Monitoring sleep interval in minutes; default 5. Choose a positive value.
   Work performed during a pass adds to the total time between passes.

``dirac_api_url``
   Private DIRAC HTTP origin, default ``http://dirac-daemon:18861`` when no
   monitoring configuration supplies one. It must resolve from the monitoring
   process, not just from your browser.

``cert`` / ``key``
   Client PEM credentials for the monitoring daemon's external HTTPS health
   check. These do not configure the separate DIRAC runtime's proxy.

``verify`` / ``trusted_cas``
   External HTTPS trust settings. A non-empty ``trusted_cas`` overrides the
   boolean verification setting with a CA bundle/directory path.
   Verification defaults to False on the CLI, so explicitly enable it or
   supply the correct trust store in production.

``dirac.api_host`` / ``dirac.api_port``
   DIRAC REST bind address. The CLI defaults to host ``dirac-daemon`` and port
   ``18861``. For a native single-host deployment set the host to
   ``127.0.0.1`` explicitly. Container deployments can use the Compose service
   hostname on their private network.

``parametricjobs.reschedules``
   Maximum automatic rescheduling count per failed/stalled DIRAC job, default 2.
   The automatic path also requires at least one ``DONE`` job in the same
   group. Set to 0 to disable automatic attempts; manual retries have different
   eligibility rules.

Path handling and secrets
--------------------------

The selected configuration path is expanded for user/environment variables.
TLS file paths are also expanded by the HTTP utility. Arbitrary string values
are not universally expanded: do not expect ``$DATABASE_URL`` in ``dburl`` to
be substituted from the shell automatically. Prefer absolute paths for
deployment settings.

Configuration accessors return copies, and the entry-point map is set once per
process. Editing the file does not hot-reload running daemons; restart them
in a controlled order.

At DEBUG level, shared logging prints configuration and runtime options.
Those structures can contain database credentials and provider tokens. Limit
log access, avoid unnecessary DEBUG logging in production, and redact diagnostic
output before sharing it.
