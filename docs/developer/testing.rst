Testing and validation
======================

Select the smallest useful layer
--------------------------------

Install the development extra as described in :doc:`development`.
Use an isolated database and local mocks rather than production credentials.
The tests cover utility functions, the public Python client, CLI option
handling, HTTP/TLS integration, DIRAC transport, and web routes.

Run a targeted selection first:

.. code-block:: bash

   python -m pytest tests/test_utils.py tests/test_cli.py

For isolated HTTP/TLS work:

.. code-block:: bash

   python -m pytest tests/test_http_utils.py

For public API and HTML routing work:

.. code-block:: bash

   python -m pytest tests/test_webapp.py

These commands identify relevant test areas; they are not a claim that every
historical test currently passes on every host. Review the caveats below
before relying on a full-suite result.

Existing test environment caveats
----------------------------------

* ``tests/test_api.py::TestLiveServer`` contacts an external production host
  and expects local X.509 files. Do not run it casually in offline or
  credential-free validation. To exclude that class from a targeted client
  run, use:

  .. code-block:: bash

     python -m pytest tests/test_api.py -k 'not TestLiveServer'

* DIRAC server tests import DIRAC-dependent modules during collection. Merely
  deselecting a test by keyword does not prevent collection-time imports.
  Use separate file selectors or a deliberately configured DIRAC test
  environment. Some checked-in tests refer to older injected server/client
  signatures; compare them with the current implementation when diagnosing
  baseline failures.
* Some utility path expectations are specific to a particular Windows home
  directory and ``OS`` environment variable. Treat failures on another host
  as platform-specific test assumptions, not proof of a path-expansion change.
* Temporary-manager tests and the miscellaneous placeholder test contain
  no-op methods. Their successful execution does not demonstrate lifecycle
  coverage.
* Some HTTP argument assertions predate transport changes. Compare the failure
  with the actual current API rather than rewriting production behavior solely
  to satisfy an outdated assertion.
* Pytest configuration is present under ``[tool.pytest]`` in the packaging
  file. Do not assume all installed pytest versions recognize that table or
  apply its coverage defaults; pass important selectors and options explicitly.

When reporting validation, distinguish new regressions from existing failures.
Do not silently skip an entire subsystem to make an unrelated task appear
fully tested.

Fixtures and singleton isolation
---------------------------------

The session-level configuration fixture discovers entry points once.
Another fixture clears selected model-package attributes before each test
to avoid raw submodule attributes shadowing lazily resolved classes.
Preserve those fixtures when modifying imports.

Database-oriented tests reset the session registry and create a fresh SQLite
database. The dummy user is shared module state and must be made transient
before attaching it to a new test database. If writing a new fixture, account
for session-bound ORM state and dispose of its resources after use.

Never reset a singleton by deleting its instance attribute in application
runtime code simply because a test fixture uses that technique for isolation.

Testing behavior across boundaries
-----------------------------------

For a request field change, test:

#. Creation-schema validation for accepted and rejected values.
#. ORM persistence and round-trip retrieval.
#. Public response serialization and any legacy JSON encoder path.
#. Browser preparation/preview and final wire payload.
#. Extension job-generation use of the field, where applicable.

For workflow changes, cover permission checks, invalid transitions, mixed
child states, retries, and database rollback. Ensure tests read persisted state
after API updates rather than checking only an HTTP 200 response.

For DIRAC integration, separate three failure modes:

* Network/TLS/request errors before receiving a response.
* Non-successful HTTP responses from the private service.
* HTTP success with a DIRAC ``OK=False`` result.

Mock only the necessary boundary. The HTTP/TLS regression tests retain real
HTTPX request validation while replacing the network transport. This detects
unsupported argument combinations more reliably than mocking all client
methods with unconstrained mocks.

Browser upload testing
-----------------------

The spreadsheet helper is plain browser JavaScript without a declared
JavaScript package-manager test runner. The repository includes
``tests/test_parametricjob_upload.html`` as a standalone browser regression
page. Open it in a browser with CDN access and inspect the displayed PASS/FAIL
results. It loads the helper from the checkout and does not need a running
production server.

The existing browser fixture includes older ``parametricjobs`` payload keys
while the current helper expects ``parametric_jobs``. Treat those baseline
failures as test drift to resolve in a browser-code change, not as evidence
that the old key is still accepted by the current helper. For changes to the
helper, also use a disposable web application and browser checks.

Exercise at least:

* Empty files, missing/duplicate/reserved headers, and headerless extra cells.
* Multiple worksheets and confirmation that only the first is consumed.
* Numbers, booleans, empty cells, and entirely blank rows.
* Malformed preparation output, synchronous exceptions, Promise returns,
  and non-finite numbers.
* Editing form defaults after upload, preview regeneration, and exact equality
  between preview snapshot and final payload.
* Rapid file changes, duplicate clicks, failed submission, and retry controls.
* Safe text rendering of uploaded values rather than HTML interpretation.

Code/documentation checks
--------------------------

Use installed repository tooling and targeted paths:

.. code-block:: bash

   python -m compileall -q productionsystem scripts
   python -m pycodestyle productionsystem scripts
   python -m pydocstyle --convention=google \
     --add-ignore=D212,D418 --add-select=D213 productionsystem scripts tests

The Google convention defaults to D212, so it is explicitly replaced by D213.
D418 is excluded because this repository documents overload declarations too.
The repository's pycodestyle configuration sets a 120-character limit;
baseline code may still contain unrelated findings.

For documentation-only edits, run the Sphinx builds in :doc:`documentation`
instead of launching daemon or live-server tests.
