Automating requests with Python and HTTP
========================================

Choose the right interface
--------------------------

The Python ``JSI`` client wraps common request operations. Direct HTTPS access
also exposes nested jobs, services, users, and rescheduling. These are public
application resources, distinct from the private DIRAC daemon API described
in :doc:`../developer/dirac-integration`.

Install the package in a Python 3.12-or-newer environment to use ``JSI``.
The current source uses Python 3.12 type-alias syntax. See :doc:`installation`
for full-service requirements.

Authenticate and verify the server
----------------------------------

Use your client certificate and key and an appropriate server trust store.
Do not disable verification to resolve CA installation problems.

.. code-block:: python

   import httpx

   from productionsystem.api import JSI

   client = JSI(
       "https://production.example.org",
       cert=("/home/alice/.globus/usercert.pem",
             "/home/alice/.globus/userkey.pem"),
       verify="/etc/grid-security/certificates",
   )

   try:
       requests = client.get_requests()
   except httpx.HTTPStatusError as error:
       print(error.response.status_code, error.response.text)
       raise

``verify=True`` uses the Python/OpenSSL default trust roots. A path can name
a CA bundle or an OpenSSL hashed CA directory; explicit CA material is added
to the default roots. A combined certificate/key PEM filename can be supplied
instead of the pair. The TLS helper does not accept a private-key password;
encrypted keys may prompt and are unsuitable for unattended jobs without a
separate credential-handling arrangement.

.. warning::

   ``JSI`` currently defaults to ``verify=False``. Set it explicitly to
   ``True`` or a trust-store path in production automation.

Create, find, and inspect a request
------------------------------------

.. code-block:: python

   response = client.create_request({
       "description": "Validation production",
       "parametric_jobs": [
           {"site": "ANY", "priority": 3},
       ],
   })
   print(response.status_code)

   # Creation currently returns HTTP 200 with a JSON null body, not a new ID.
   for request in client.get_requests():
       print(request["id"], request["description"], request["status"])

   # Substitute an ID from the result above.
   selected = client.get_requests(42)[0]
   print(selected["parametricjobs"])

``get_requests()`` returns a list. ``get_requests(42)`` also returns a list
with one element and performs an additional nested-job query, placing its
result under ``parametricjobs``. The public request schema already exposes
``parametric_jobs``; do not confuse that schema field with the client's
additional compatibility key.

Creation does not return a resource ID or ``Location`` header. Correlate
results carefully, especially if several requests can be created concurrently.
Neither description matching nor taking the last list entry is a reliable
uniqueness guarantee.

Administrative request methods
-------------------------------

These calls require the certificate identity to be an administrator:

.. code-block:: python

   client.approve_request(42)
   # After monitoring has finished and outputs have been reviewed:
   client.mark_checked(42)
   client.mark_closed(42)

``modify_request_status(request_id, LocalStatus)`` is the lower-level form
update wrapper. Prefer the named workflow methods and respect the transition
rules in :doc:`requests`. ``delete_request(42)`` schedules local removal;
it is not an external job cancellation guarantee.

Each operation owns a short-lived HTTPX client. Returned responses are buffered
before the connection pool closes. Failed HTTP statuses raise
``httpx.HTTPStatusError``; transport and TLS failures raise their underlying
exceptions.

Direct HTTPS examples
----------------------

The following Linux shell examples use curl. Replace the URL and paths before
running them. A public request uses JSON for creation and URL-encoded forms
for updates:

.. code-block:: bash

   curl --fail-with-body \
     --cert "$HOME/.globus/usercert.pem" --key "$HOME/.globus/userkey.pem" \
     --capath /etc/grid-security/certificates \
     https://production.example.org/api/requests

.. code-block:: bash

   curl --fail-with-body \
     --cert "$HOME/.globus/usercert.pem" --key "$HOME/.globus/userkey.pem" \
     --capath /etc/grid-security/certificates \
     -H 'Content-Type: application/json' \
     --data '{"request":{"description":"Validation production","parametric_jobs":[{"site":"ANY","priority":3}]}}' \
     https://production.example.org/api/requests

.. code-block:: bash

   curl --fail-with-body \
     --cert "$HOME/.globus/usercert.pem" --key "$HOME/.globus/userkey.pem" \
     --capath /etc/grid-security/certificates \
     -X PUT --data-urlencode 'reschedule=true' \
     https://production.example.org/api/requests/42/parametricjobs/1

Use ``--cacert /path/to/ca-bundle.pem`` instead of ``--capath`` for a bundle.
Do not add ``--insecure`` to production examples.

Resource map
-------------

All paths below are relative to the public origin:

.. list-table::
   :header-rows: 1
   :widths: 12 53 35

   * - Methods
     - Path
     - Access and purpose
   * - GET, POST
     - ``/api/requests``
     - Registered user: list visible requests or create one.
   * - GET
     - ``/api/requests/{request_id}``
     - Owner or administrator: request detail.
   * - PUT, DELETE
     - ``/api/requests/{request_id}``
     - Administrator: change status or schedule removal.
   * - GET
     - ``/api/requests/{request_id}/parametricjobs``
     - Owner or administrator: list groups.
   * - GET, PUT
     - ``/api/requests/{request_id}/parametricjobs/{parametricjob_id}``
     - Owner or administrator: detail or reschedule form.
   * - GET
     - ``/api/requests/{request_id}/parametricjobs/{parametricjob_id}/diracjobs``
     - Owner or administrator: external job summaries.
   * - GET
     - ``/api/requests/{request_id}/parametricjobs/{parametricjob_id}/diracjobs/{diracjob_id}``
     - Owner or administrator: one external job.
   * - GET
     - ``/api/services`` and ``/api/services/{service_id}``
     - Administrator: recorded health checks.
   * - GET
     - ``/api/users`` and ``/api/users/{user_id}``
     - Administrator: registered identities.
   * - PUT
     - ``/api/users/{user_id}``
     - Administrator: ``admin=true`` or ``admin=false`` form.

List endpoints return arrays, not pagination envelopes. Statuses are displayed
as names such as ``"Requested"`` rather than integer enum values. Update
handlers commonly return JSON null on HTTP 200; read the resource afterward
instead of treating a missing response object as a failure.

FastAPI normally exposes generated interactive documentation at ``/docs`` and
the schema at ``/openapi.json`` on the public web application, subject to proxy
policy. The repository also contains a downloadable
:download:`OpenAPI document <../openapi/openapi.yaml>`, but the running
application's generated schema is the better description of installed routes
and extensions. No authentication bypass is provided by the schema UI.

Repository and CVMFS listings
------------------------------

Authenticated listing endpoints are available to registered users and are
often used by extension-defined request forms:

.. list-table::
   :header-rows: 1

   * - POST path
     - Purpose
   * - ``/gittags/{owner}/{repo}``
     - List repository tags using the operator-configured provider.
   * - ``/git/{owner}/{repo}``
     - List the root directory at a selected reference.
   * - ``/git/{owner}/{repo}/{path}``
     - List a subdirectory at a selected reference.
   * - ``/cvmfs/{path}``
     - List the corresponding path below the server's ``/cvmfs`` mount.

Send a JSON object rather than a URL-encoded form. For example, a Git directory
listing body can be:

.. code-block:: json

   {
     "tag": "main",
     "regex": ".*",
     "type": "files",
     "sort": true
   }

``tag`` is the Git reference name; the built-in default is ``master``, not
automatically the repository's default branch. ``type`` accepts ``files``,
``dirs``, or ``all``. Git directory regex defaults to ``.*``; CVMFS requires
an explicit ``regex`` key. The provider/local-checkout base path is configured
by the operator and cannot be selected arbitrarily by this request.

Tag listings accept sorting controls but not the directory regex/type/tag
options. ``sort`` and ``sort-reversed`` are JSON booleans and cannot both be
true. ``sort-type`` can be null or ``"versions"``; version sorting requires
names accepted by the packaging version parser. Without a sorting flag, the
provider's result ordering is not guaranteed.

Results are arrays of strings, not full provider metadata. Directory regexes
match from the start of a name. For matching directory entries, a capturing
group can change the returned text to the last group; matching file entries
return the whole match. Keep regexes simple unless an extension explicitly
depends on that extraction behavior.

The built-in provider requests do not implement general paginated traversal.
Do not assume a listing includes every tag or file in a very large remote
repository. Missing repositories, references, inaccessible local mounts, or
provider failures should be diagnosed from the HTTP detail and server logs.

Retry policy
-------------

GET requests can normally be retried after transient network failures.
For POST creation, inspect existing requests before retrying. For state updates,
read the current state after a timeout; the update may already have committed.
Handle HTTP 409 as a workflow conflict, not a retryable transport error.
See :doc:`troubleshooting` for the other common response codes.
