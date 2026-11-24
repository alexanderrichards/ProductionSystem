Building and maintaining documentation
======================================

Three parallel documentation layers
------------------------------------

The Sphinx root links:

* ``user/``: task-oriented request usage, API automation, deployment, and
  operational guidance.
* ``developer/``: architecture, extension contracts, data/session behavior,
  testing, and documentation maintenance.
* ``productionsystem*.rst``: Python/module and command-source reference pages.

Keep conceptual explanations and end-to-end examples in the guides.
Keep signatures, individual parameters, and callable return/exception details
in Python docstrings. A behavior change can require edits to both layers.

Build locally
--------------

From the repository root in the selected Python environment:

.. code-block:: bash

   python -m pip install -e '.[doc]'
   python -m sphinx -b html -W --keep-going docs docs/_build/html

Open ``docs/_build/html/index.html`` to inspect the generated navigation,
tables, code examples, admonitions, and cross-links. On systems with Make,
``make -C docs html`` is a convenience wrapper, but explicit warning options
are preferable for validation.

``-W`` makes warnings fail the build;
``--keep-going`` collects additional diagnostics instead of stopping at the
first warning.

After changing reference-module names or removing exported objects, validate
in a fresh output directory. Reusing an old HTML tree can retain obsolete
generated source pages or anchors even when the new sources build successfully.

Add ``-n`` for an additional nitpicky audit of Python cross-references. The
legacy API docstrings contain type names that are not all resolvable Sphinx
targets, so that audit can report reference debt independently of a normal
warning-clean build. Do not suppress missing guide links to hide type warnings.

Other useful builders:

.. code-block:: bash

   python -m sphinx -b doctest docs docs/_build/doctest
   python -m sphinx -b linkcheck docs docs/_build/linkcheck

Doctest checks examples explicitly marked as doctests; ordinary ``code-block``
examples are not automatically executed. Linkcheck contacts external services
and may fail on private sites, authentication requirements, or rate limits.
Review those failures separately from broken internal document references.

Documentation builds do not need a running database, Apache, or DIRAC service.
The Sphinx configuration initializes only configuration/entry-point discovery,
not the SQL session registry. It mocks ``DIRAC`` and ``daemonize`` imports for
reference generation on hosts without those runtime dependencies. These mocks
are documentation-only and do not test daemon behavior.

Normal publishing uses the configured Python documentation intersphinx
inventory. A disconnected build may warn if that external inventory is not
cached; distinguish that connectivity problem from broken local guide links.

Read the Docs
--------------

The repository's ``readthedocs_requirements.txt`` installs ``-e .[doc]``.
Configure the Read the Docs project to use a compatible Python version,
install that requirements file, and build with ``docs/conf.py``.
If configuring builds through a project-level Read the Docs YAML file, keep
those same requirements; this repository does not currently include such a
YAML file.

Do not add real deployment configuration, certificates, or running-service
requirements to the documentation build. Reference generation should remain
safe in a clean, credential-free publishing environment.

RST authoring conventions
--------------------------

Use descriptive headings, stable page filenames, and relative Sphinx links:

.. code-block:: rst

   Example chapter
   ===============

   Explain the task and its prerequisites.

   See :doc:`../user/configuration` for the corresponding deployment settings.

   .. code-block:: python

      print("A small, complete example")

Use ``:doc:`` for another page, ``:ref:`` for a labeled section, and
``:download:`` for a source artifact. Add new chapters to their guide's
``index.rst`` toctree; an orphan file will not appear in the intended navigation.
Use list tables for compact setting/resource comparisons and warnings for
destructive or unsafe operations.

Examples should:

* Name the target shell/interpreter where it matters.
* Use placeholder hostnames and identities, never working credentials.
* State whether a command is read-only, creates work, or can delete data.
* Include required initialization for snippets using lazy models.
* Match actual CLI options and HTTP request/response shapes.
* Distinguish recommended deployment practice from behavior enforced by code.
* Explain limitations rather than inventing missing functionality.

Keep Python docstrings in Google style with D213 summary placement.
``sphinx.ext.napoleon`` renders ``Args``, ``Returns``, ``Yields``,
``Raises``, and ``Attributes`` sections. Do not change docstrings to D212 as
part of regenerating reference pages.

Review checklist
-----------------

#. Build all documentation, not only the new chapter.
#. Confirm both guide trees and the API reference remain reachable from the root.
#. Follow links in the generated HTML and check long endpoint tables on a
   narrow viewport.
#. Validate non-destructive examples against current code or isolated fixtures.
#. Check that production examples enable TLS verification and that mock/reset
   examples carry clear warnings.
#. Keep generated HTML and build caches out of source control.
#. Record any external link or existing reference limitation honestly.
