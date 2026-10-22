Developing extensions
=====================

Extension discovery
--------------------

Production System discovers installed distribution entry points in four groups:

.. list-table::
   :header-rows: 1

   * - Group
     - Common names
     - Purpose
   * - ``dbmodels``
     - ``requests``, ``parametricjobs`` and schema names
     - Replace selected request/job classes and their input/output schemas.
   * - ``monitoring``
     - ``daemon``
     - Replace the monitoring daemon.
   * - ``webapp``
     - ``daemon``, optional ``jinja2_loader``
     - Replace the web daemon or supply template loading.
   * - ``webapp.services``
     - ``htmlpageserver``
     - Replace the HTML service.

The base package registers ``requests`` and ``parametricjobs`` in ``dbmodels``
and the three daemon/service entries shown in its packaging metadata.
The model resolver additionally recognizes ``request``, ``requestcreate``,
``parametricjob``, and ``parametricjobcreate`` entry names when supplied by an
extension. Names are resolved by lowercasing the exported class/schema name.

Discovery identifies a project using the top-level module named by an entry
point. Install the extension distribution in every relevant environment and
restart processes after changing metadata.

.. important::

   The current discovery helper merges every installed extension project,
   replacing complete group mappings with ``dict.update``. The ``--extension``
   option validates that a name was discovered; it does not isolate loading
   to that one extension. Do not install competing implementations of the
   same group and assume the option chooses a deterministic winner. Provide
   the complete group mapping your deployment needs and test the resolved map.

The fixed models/schemas ``Services``, ``Service``, ``Users``, ``User``,
``DiracJobs``, and ``DiracJob`` always use built-in definitions.

A minimal job-generation extension
-----------------------------------

The following example changes only generated job behavior, without adding
columns or custom API fields. Place it in an installed package, for example
``example_production/models.py``:

.. code-block:: python

   from productionsystem.sql.models.ParametricJobs import ParametricJobs


   class ExampleParametricJobs(ParametricJobs):
       """
       Generate a small validation workload.

       Use the inherited fields and single-table polymorphic mapping.
       """

       __mapper_args__ = {"polymorphic_identity": "example_parametricjobs"}

       def _setup_dirac_job(self, DiracJobClass, tmp_runscript, tmp_dir):
           """
           Record a DIRAC job using the managed input sandbox.

           Args:
               DiracJobClass: Recorder class supplied by the submission context.
               tmp_runscript: Writable managed executable script.
               tmp_dir: Owning managed directory, available for auxiliary files.

           Returns:
               list: Recorded job definitions to submit.
           """
           tmp_runscript.write("#!/bin/bash\nset -eu\nprintf 'validation\\n'\n")
           tmp_runscript.flush()
           job = DiracJobClass()
           job.setName(f"Validation {self.request_id}.{self.id}")
           job.setExecutable("runscript.sh")
           job.setInputSandbox([tmp_runscript.name])
           job.setPriority(self.priority)
           return [job]

Register it in the extension's ``pyproject.toml``:

.. code-block:: toml

   [project.entry-points.dbmodels]
   parametricjobs = "example_production.models:ExampleParametricJobs"
   requests = "productionsystem.sql.models.Requests:Requests"

The extension still needs normal package/build metadata and a dependency on
the compatible Production System version. The example explicitly retains the
built-in request entry because group mappings are replaced during discovery.
If replacing other groups, include their required names too.

The setup hook receives a writable, already-created ``runscript.sh`` and a
managed directory. Flush buffered content before submission. Return a list
of recorded jobs, even for one job. Create auxiliary resources through the
provided manager, and keep all sandbox paths visible at the same absolute
locations to the DIRAC process until submission completes.

The recorder does not execute job setters locally and does not return values
from them. It stores JSON-compatible method names/arguments for remote replay.
Do not pass open file objects, custom Python instances, or functions as
recorded arguments. The example applies priority but intentionally does not
implement site routing or real scientific output handling; add and test those
against the installed DIRAC API before treating it as a production workload.

Adding custom fields
---------------------

For experiment-specific data:

#. Define the ORM mapping and a unique polymorphic identity. Plan storage and
   migrations rather than assuming table creation updates an existing schema.
#. Extend the relevant creation schema to validate accepted inputs.
#. Extend the relevant response schema to expose intended outputs.
#. Register the lowercased schema names in ``dbmodels`` alongside the ORM
   entries. Verify that ``RequestCreate`` actually uses the intended nested
   parametric-job creation type.
#. Update templates or spreadsheet preparation to produce those fields.
#. Test end-to-end creation, persistence, response serialization, and job setup.

Avoid creating a second mapping of an already mapped table. Use the existing
declarative base and the intended SQLAlchemy inheritance pattern.
Import base implementation classes from their defining modules when defining
an override so that resolving an entry point does not recursively resolve
itself through the package-level lazy loader.

Template customization
----------------------

The web startup script optionally loads a ``jinja2_loader`` entry point from
the ``webapp`` group. The loader is an object, not a factory invoked by the
startup script. For example, an extension module can export:

.. code-block:: python

   from jinja2 import PackageLoader

   template_loader = PackageLoader("example_production", "templates")

Register that object together with the web daemon entry:

.. code-block:: toml

   [project.entry-points.webapp]
   daemon = "productionsystem.webapp.WebApp:WebApp"
   jinja2_loader = "example_production.templates:template_loader"

Package the extension's template files in its distribution. The HTML service
searches a ``productionsystem``-prefixed base loader, then the extra loader,
then the unprefixed packaged templates. This permits an extension template to
extend the original without recursively loading itself:

.. code-block:: jinja

   {% extends "productionsystem/newrequest_template.html" %}

   {% block title %}Experiment production request{% endblock %}

Use existing named template blocks instead of copying entire pages.
The new-request page exposes blocks including ``form_content``,
``parametricjobs_content``, ``create_request``, and ``document_ready_js``.

Spreadsheet preparation contract
---------------------------------

The ``create_request`` block runs inside a synchronous JavaScript function
receiving the jQuery form and a deep copy of parsed spreadsheet rows. Return
a request object, not the outer ``{"request": ...}`` wire wrapper:

.. code-block:: javascript

   form_data.parametric_jobs = excel_rows.map(function (row) {
       return {
           site: row.site || form_data.site,
           priority: row.priority === undefined
               ? Number(form_data.priority) : row.priority
       };
   });
   return form_data;

This optional transformation explicitly applies form defaults to rows; the
base template does not do that automatically.

Do not return a Promise, mutate upload-manager state, or make background network
requests to complete preparation. The upload manager serializes/normalizes the
result, rejects non-finite numbers and invalid job-array shapes, freezes the
snapshot, and uses that same snapshot for preview and submission.
Do not read mutable form values again when sending the final request.

If extra client-side files are required, arrange their serving explicitly.
Providing a Jinja loader does not automatically expose an extension's static
directory.

Service and daemon overrides
-----------------------------

An HTML service override must preserve the constructor contract used by web
startup, including ``extra_jinja2_loader``, and expose a compatible ``router``.
A daemon override must accept the options passed by its command script.
New API routes should use existing verified-user/admin dependencies and
Pydantic schemas rather than reading identity headers ad hoc.

Verify resolved entry points, imports, and mapper setup in a fresh process
before starting a real monitor. See :doc:`testing` for the required layers of
coverage.
