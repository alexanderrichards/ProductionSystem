Setting up a development environment
=====================================

Local checkout and dependencies
-------------------------------

Use a disposable environment and database. The main code requires Python 3.12
or newer; use the same interpreter version as your intended deployment when
possible. Linux is the natural development host for the complete daemon stack.

.. code-block:: bash

   git clone https://github.com/alexanderrichards/ProductionSystem.git
   cd ProductionSystem
   python3.12 -m venv .venv
   . .venv/bin/activate
   python -m pip install -e '.[dev]'

For documentation-only work, ``python -m pip install -e '.[doc]'`` is sufficient.
Editable installation is required for realistic entry-point behavior: adding
the source tree to an import path does not create distribution metadata.

On Windows, documentation and isolated utility/client work can use:

.. code-block:: powershell

   py -3.13 -m venv .venv-windows
   .\.venv-windows\Scripts\Activate.ps1
   python -m pip install -e ".[dev]"

Do not share the same virtual environment directory between Linux and Windows.
Run the full POSIX daemon workflow in WSL or Linux containers. A successful
import of a client module does not establish native Windows support for
``daemonize``.

Decide what needs to run
------------------------

For utility or serialization changes, start with targeted tests and an isolated
SQLite database. For HTML/REST work, mount real routers with a dummy-user
dependency as the web tests do; an external Apache process is unnecessary for
that test layer.

For end-to-end submission work, use a configured DIRAC environment, shared
sandbox paths, and a controlled execution identity. Do not test job-generation
changes by attaching a development monitor to a production database.

The local web demonstration in :doc:`../user/installation` is useful for layout
and request creation but resets its working-directory database on every mock
startup. It is not an end-to-end DIRAC simulator.

Compose development overlay
---------------------------

The development Compose overlay changes build targets and bind-mounts the
checkout at ``/root/ProductionSystem``. Its install wrapper activates the
appropriate Python environment and installs the mounted package editably
before starting a command.

From the repository's ``docker`` directory:

.. code-block:: bash

   ./compose-dev.sh config
   ./compose-dev.sh up --build -d
   ./compose-dev.sh logs --tail=100 webapp monitoring-daemon dirac-daemon

The same private ``.env``, database, credential, and site-configuration
requirements apply as in :doc:`../user/installation`. This overlay is not a
credential-free test environment, and it uses the same Compose project name
and named volumes as the supplied stack. Use an isolated deployment context;
do not assume adding the overlay creates separate production-safe storage.

Source edits in the bind mount are visible immediately, but the daemons are
not configured with automatic reload. Restart affected services to load code
changes. Reinstall/restart when entry-point metadata changes.

Work safely with configuration
-------------------------------

Use a dedicated INI file, absolute local database paths, and distinct PID/log
directories. Set ``monitoring.dirac_api_url`` in the file. Keep model extensions
consistent across web and monitoring processes.

Before starting any monitor:

#. Print or inspect the selected database location locally without sharing
   secrets.
#. Verify the configured DIRAC endpoint and execution account.
#. Confirm that it will not pick up existing production ``Approved`` requests.
#. Confirm temporary sandbox visibility from both processes.

To debug a loop interactively, pass ``--debug-mode -v`` or ``-vv`` to the
selected start command. Foreground mode and logging verbosity are independent.

Repository conventions
-----------------------

Follow the existing module/class naming when modifying the legacy table and
daemon modules. New Python documentation uses Google-style sections and D213
layout:

.. code-block:: python

   def describe_request(request_id: int) -> str:
       """
       Return a display label for a request.

       Args:
           request_id (int): Production request identifier.

       Returns:
           str: Human-readable label.
       """
       return f"Request {request_id}"

Use ``Yields`` for generators/context managers and document meaningful
exceptions at the layer that exposes them. Keep narrative guides in RST and
link them through the appropriate guide index. Do not change existing
docstrings to D212 merely to satisfy a linter's default convention.

The repository has historical tests and deployment examples that can drift
from the implementation. Verify behavior at the current signatures and route
handlers, not only in a checked-in OpenAPI snapshot or an older README example.
