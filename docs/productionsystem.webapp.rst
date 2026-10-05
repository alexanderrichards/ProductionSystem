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

``ParametricJobUpload`` stores parsed data in ``excel_rows`` and exposes it
through ``getExcelRows()``. The submission handler passes those rows to
``create_request(form_data, excel_rows)``. Overrides of the ``create_request``
Jinja block are responsible for transforming the rows into parametricjobs and
assigning ``form_data["parametricjobs"]``. The default hook uses the rows
directly, preserving the existing API envelope. The preview displays the
parsed Excel rows, not the parametricjobs produced by a custom hook.

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

After a successful upload, a preview shows the total parsed Excel row count,
the fields present across all rows, and values from the first and last rows
(only one example for a single-row file). Missing example values are marked as
omitted, and fields empty in every row are not listed. Values use JSON notation
to distinguish strings, numbers and booleans. Values longer than 200 characters
are shortened in the preview only; the submitted data is unchanged. Changing
or clearing the file removes the old preview while the new file is read.

Enter a single row number and click "Show row" (or press Enter in the selector)
to replace the default examples with that row. Numbers are 1-based positions
in ``excel_rows``, excluding empty data rows, not worksheet row numbers.
Ranges, fractions and out-of-bounds numbers display an error without changing
the existing preview or submitted data. "Show first and last" restores the
default preview. Each new upload resets the selection.

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
