Creating and managing requests
==============================

Using the dashboard
--------------------

The request table shows the ID, description, state, request time, and requester.
Administrators see all requests; other users see their own. Use table searching
and sorting to find a request. Expand a row with its chevron to inspect its
parametric jobs and their submitted, running, completed, and failed counts.

Right-click a request row to open its context menu. **Info** shows request
metadata and parametric-job details. **Log** shows client-visible lifecycle
messages. Administrators also see approval, checking, closure, and removal
actions. Bulk selection can apply administrative actions to multiple requests;
each request is still processed separately. A bulk action is not one atomic
database transaction.

The standard dashboard includes an **Export** button, but the built-in template
does not implement an export workflow. Use the API to retrieve data rather than
assuming that button downloads a file.

Preparing the spreadsheet
-------------------------

The standard new-request form accepts ``.xlsx``, ``.xls``, and ``.csv`` files.
It reads the file in your browser with SheetJS and uses only the first
worksheet. The uploaded file itself is not stored by the server; the resulting
JSON request is submitted.

For the built-in schema, a minimal CSV is:

.. code-block:: text

   site,priority
   ANY,3
   LCG.UKI-LT2-IC-HEP.uk,2

Each non-empty data row becomes one parametric job. The built-in creation
schema accepts ``site`` and ``priority``; extension-defined columns require
matching extension support. Do not assume that arbitrary spreadsheet columns
are persisted. The built-in priority database constraint permits integers
from 0 through 9, with 3 as the default. The default site is ``ANY``.

Follow these formatting rules:

* Put field names in the first row. Leading and trailing whitespace in headers
  is removed; duplicate or empty headers are rejected.
* Give every populated column a header. Data beyond the header row's width is
  rejected.
* Include at least one non-empty data row. Entirely empty rows are ignored.
* Empty cells are omitted rather than sent as explicit null values.
* Use real spreadsheet numbers and booleans for typed values. Check the preview
  especially carefully when importing CSV, where inferred types may differ.
* Do not use the reserved names ``__proto__``, ``constructor``, or ``prototype``
  as headers.

.. note::

   Extensions can transform the parsed rows before submission. The form's
   top-level site and priority values are separate from the spreadsheet rows.
   In the built-in form, rows are assigned directly to ``parametric_jobs``;
   top-level values are not automatically copied into every job.

Inspecting the preview
----------------------

The preview lists fields found across the generated jobs and shows the first
and last job by default. A single-job request has one example. Enter a whole
job number and choose **Show job** (or press Enter) to inspect that job;
**Show first and last** restores the default view.

Job numbers are 1-based positions in the generated ``parametric_jobs`` array,
not Excel row numbers or assigned database IDs. Ranges and fractional or
out-of-bounds values are rejected without changing the prepared request.
Missing values are marked as omitted. JSON notation distinguishes strings,
numbers, and booleans. Values longer than 200 characters are shortened only
in the preview, not in the submitted payload.

Changing the file clears the old preview while the replacement is read.
Changing a named form input rebuilds the prepared snapshot and resets the
preview selection. If an extension produces an empty job list, the preview can
show zero generated jobs even though the uploaded worksheet contained rows.
Confirm that the generated result represents the workload you intended.

Submitting safely
-----------------

#. Select **New Request** and enter a meaningful description.
#. Select the spreadsheet and wait for parsing to finish.
#. Inspect the parametric-job count, columns, and values in the preview.
   If preparation fails, correct the file or form rather than bypassing the
   disabled submit button.
#. Submit once. While the request is in flight, submission and file selection
   are disabled to reduce accidental duplicates.
#. After success, confirm that the dashboard lists the expected request and
   inspect its parametric jobs.

The preview is a snapshot of the prepared request. Editing named form fields
regenerates it. The preparation hook is synchronous; asynchronous extension
hooks are rejected. Server-side validation is still authoritative.

A network timeout is ambiguous: the server may already have created the request.
Check the request list before retrying. Request creation has no built-in
idempotency key. Keep your spreadsheet locally if you need an input record.

Lifecycle and review
--------------------

The normal review path is:

.. code-block:: text

   Requested -> Approved -> Submitting -> Submitted / Running
                                           |
                                    Completed or Failed
                                           |
                                        Checked -> Closed

This diagram is a workflow overview, not a promise that every intermediate
state appears. Monitoring can move directly to a later observed state.

.. list-table:: States visible to users
   :header-rows: 1
   :widths: 20 80

   * - State
     - Meaning and next action
   * - Requested
     - Stored but not approved. Ask an administrator to review it.
   * - Approved
     - Eligible for submission on a monitoring pass.
   * - Submitting
     - Submission or a requested reschedule is being processed.
   * - Submitted
     - External jobs have been received or queued by DIRAC.
   * - Running
     - Work is active, or DIRAC is still finalizing it.
   * - Completed
     - External job states map to local completion. Validate scientific or
       production outputs separately.
   * - Failed
     - Some work failed, stalled, or failed during setup/submission. Inspect logs.
   * - Unknown
     - The system lacks usable state information, for example when no external
       jobs are associated with a group.
   * - Checked
     - An administrator has recorded review of a completed or failed request.
   * - Closed
     - An administrator has closed an already checked request.
   * - Removing
     - Scheduled for deletion and external-job cleanup on a monitoring pass.
   * - Killed / Deleted
     - Local representations of corresponding external DIRAC states.

Approval is permitted only from ``Requested``. Marking checked is permitted
only from ``Completed`` or ``Failed``. Closing is permitted only from
``Checked``. Invalid attempts return HTTP 409 and do not perform the requested
transition. These are the explicitly guarded review transitions; the API is
not a general-purpose fully constrained state machine.

Aggregate states are not percentages: the built-in implementation combines
states using the numeric ordering of local status values. A request may still
show ``Running`` while some of its jobs have already failed. Inspect counters
and child jobs rather than relying on the parent label alone.

Rescheduling failed work
------------------------

Use the reschedule icon for an eligible failed parametric job, or the form API
described in :doc:`automation`. The handler acts when the group is ``Failed``,
``reschedule`` is true, and a reschedule is not already pending. It sets the
group and parent request to ``Submitting`` and leaves the actual DIRAC
rescheduling to monitoring.

Only failed or stalled external jobs are selected for manual rescheduling.
Successful jobs are not recreated. An accepted HTTP response outside the
eligibility conditions can be a no-op; inspect the subsequent job state.
Automatic rescheduling has additional conditions and a configured retry count;
see :doc:`operations`.

Removing a request
-------------------

Only an administrator can schedule removal. The DELETE operation marks a
request ``Removing``; it does not synchronously remove the row. The monitoring
daemon later deletes the request and its dependent local records.
Deleting a persistent parametric-job group triggers a SQLAlchemy session event
that attempts to kill and delete its associated DIRAC jobs.

.. warning::

   External cleanup and local database deletion are not one atomic operation.
   The cleanup helper logs some remote failures and can leave external jobs
   orphaned; other failures can interrupt local removal. Do not use a missing
   request row as proof that every external job stopped or its output was
   removed. Preserve external IDs and verify cleanup with your DIRAC operator.

There is no built-in restore or undelete endpoint. Preserve necessary IDs,
logs, output references, and database backups before removal.
