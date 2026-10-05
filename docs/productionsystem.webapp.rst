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

Use the first row for JSON field names, such as ``site``, ``priority``, and any
fields supported by the configured parametricjob model. Each subsequent
non-empty row becomes one object in ``request.parametricjobs``. Headers must be
non-empty and unique (surrounding whitespace is trimmed). Empty cells are
omitted, leaving existing server defaults in effect. Numbers and booleans
should be stored as native Excel values; text is preserved as text. Additional
worksheets are ignored.

For example, a worksheet containing:

.. list-table::
   :header-rows: 1

   * - site
     - priority
   * - ANY
     - 3
   * - LCG.UKI-LT2-IC-HEP.uk
     - 5

produces the same API envelope as before:

.. code-block:: json

   {"request": {"description": "Example request", "site": "ANY", "priority": "3",
                "parametricjobs": [{"site": "ANY", "priority": 3},
                                   {"site": "LCG.UKI-LT2-IC-HEP.uk", "priority": 5}]}}

The Excel reader uses SheetJS, loaded from the same CDN as the Excel example.
An unreadable, empty, or invalid workbook blocks submission and displays an
error in the form. API failures leave the form open for retry.

To run the browser regression tests, open
``tests/test_parametricjob_upload.html`` in a browser with CDN access. These
tests exercise real XLS/XLSX workbooks, value types, invalid uploads and
overlapping file reads.

Subpackages
-----------

.. toctree::

    productionsystem.webapp.services

Submodules
----------

.. toctree::

   productionsystem.webapp.WebApp
   productionsystem.webapp.jinja2_utils
