productionsystem.webapp package
===============================

.. automodule:: productionsystem.webapp
    :members:
    :undoc-members:
    :show-inheritance:

Creating requests from Excel
---------------------------

The new-request form still collects request-level information manually. Upload
an ``.xlsx`` or ``.xls`` workbook to configure its parametricjobs. The browser
reads the first worksheet; the workbook itself is never uploaded to the server.

Use the first row for column names expected by the request setup hook, such as
``site`` and ``priority``. Each subsequent non-empty row becomes an object in
``excel_rows``. Headers must be non-empty and unique (surrounding whitespace is
trimmed). Empty cells are omitted from the parsed rows. Numbers and booleans
should be stored as native Excel values; text is preserved as text. Additional
worksheets are ignored.

``ParametricJobUpload`` stores parsed data in ``excel_rows``. Request
preparation passes a jQuery form and copied
rows to ``create_request(form, excel_rows)``. The callback is bound with a null
receiver, not the upload instance: strict functions see ``this === null`` and
non-strict functions see the global object. Hooks should use their supplied
arguments; this avoids accidental instance access but is not a sandbox.
The template collects ``form_data`` using ``form.serializeArray()`` before
running the hook block. Overrides of the ``create_request``
Jinja block are responsible for transforming the rows into parametricjobs and
assigning ``form_data["parametricjobs"]``. The default hook uses the rows
directly, preserving the existing API envelope. After upload and whenever
named request inputs change, the hook is called to prepare the request. Hooks
should be synchronous and free of external side effects. Each call receives a
fresh copy of the uploaded rows so mutations do not alter later calls.

The preview displays ``parametricjobs`` from the serialized request returned
by the hook, not the raw Excel rows. The plain request is normalized through
JSON serialization, deeply frozen, and stored in ``payload``. Submission adds
the ``request`` envelope without calling the hook again. Hook
errors, serialization errors or a missing/malformed ``parametricjobs`` array
display an error and block submission until the request can be prepared.

``ParametricJobUpload`` takes ``(input, status, submit_button, summary, form,
create_request)``. The callback is required and must return the plain request
object, not an object already wrapped in ``request``. The form is explicitly
required and accepts either a native form element or a jQuery form
containing exactly one form. It uses jQuery to listen for changes to
named inputs, including dynamically added fields. The template supplies the
request-building callback and handles the AJAX response. ``prepareSubmission()``
returns the prepared JSON and disables upload/submission controls; it returns
``null`` if a submission is already pending. While pending, form changes and
file reads do not replace the preview or cached request. On an API failure,
``allowRetrySubmission()`` restores file selection and prepares a fresh request from
the current form values.

No payload remains available after a failed preparation, invalid upload or
cleared file selection. Submission without a valid preview throws before
locking the controls. Circular values, BigInt and non-finite numbers are
rejected; undefined object properties are omitted as in JSON. These client-side
checks do not replace server-side validation. AJAX transport failures and
synchronous send exceptions restore retry controls and display an error.

For example, a worksheet containing:

.. list-table::
   :header-rows: 1

   * - site
     - priority
   * - ANY
     - 3
   * - LCG.UKI-LT2-IC-HEP.uk
     - 5

produces the same API envelope as before when using the default hook:

.. code-block:: json

   {"request": {"description": "Example request", "site": "ANY", "priority": "3",
                "parametricjobs": [{"site": "ANY", "priority": 3},
                                   {"site": "LCG.UKI-LT2-IC-HEP.uk", "priority": 5}]}}

The Excel reader uses SheetJS, loaded from the same CDN as the Excel example.
An unreadable, empty, or invalid workbook blocks submission and displays an
error in the form. API failures leave the form open for retry.

After a successful upload, the status shows the loaded Excel row count and
worksheet name. Below it, the preview shows the generated parametricjob count,
fields present across those jobs, and values from the first and last jobs
(only one example for a single-job request). Missing example values are marked
as omitted; fields ignored by the hook or omitted during JSON serialization
are not listed. Values use JSON notation
to distinguish strings, numbers and booleans. Values longer than 200 characters
are shortened in the preview only; the submitted data is unchanged. Changing
or clearing the file removes the old preview while the new file is read.

Enter a single job number and click "Show job" (or press Enter in the selector)
to replace the default examples with that job. Numbers are 1-based positions
in the generated ``parametricjobs`` list, not worksheet row numbers.
Ranges, fractions and out-of-bounds numbers display an error without changing
the existing preview or submitted data. "Show first and last" restores the
default preview. Each new upload or request-field change resets the selection.
An empty generated job list shows a count of zero without examples or selectors.

To run the browser regression tests, open
``tests/test_parametricjob_upload.html`` in a browser with CDN access. These
tests exercise real XLS/XLSX workbooks, value types, invalid uploads and
overlapping file reads, and bounded first/last previews for large uploads.

Subpackages
-----------

.. toctree::

    productionsystem.webapp.services

Submodules
----------

.. toctree::

   productionsystem.webapp.WebApp
   productionsystem.webapp.jinja2_utils
