Getting access and understanding the system
===========================================

What the system manages
-----------------------

Production System is a coordination layer, not an execution cluster. It stores
requests in a SQL database and asks a DIRAC environment to submit and inspect
jobs. There are three important levels:

Request
   A description of a production activity owned by a registered user. A request
   contains one or more parametric jobs and has an overall lifecycle state.

Parametric job
   A configurable group of work belonging to a request. Each group can create
   one or more external DIRAC jobs. Its ID is local to its parent request:
   request ``42``, parametric job ``1`` is often displayed as ``42.1``.

DIRAC job
   An external job identified by its DIRAC job ID. Production System stores its
   last observed state and rescheduling count. Its executable and output are
   managed by the DIRAC workflow, not by the web server.

The built-in job generator submits a small ``HelloWorld`` shell script.
Production workloads normally require an experiment-specific extension.
The presence of a site or priority field does not by itself guarantee that a
particular extension applies it to the generated DIRAC job.

Before opening the application
------------------------------

Ask your service administrator for:

#. The public HTTPS URL and any required VPN or network access.
#. A valid X.509 client certificate and private key in the format required by
   your browser or HTTP client.
#. Registration of your certificate's distinguished name (DN) and issuing
   certificate authority (CA) in the local user database.
#. Current, non-suspended virtual-organization membership.
#. The accepted request fields, spreadsheet template, allowed sites, and output
   validation procedure for the installed extension.

There is no built-in username/password login or self-service account creation.
Apache validates the certificate and forwards its verified identity to the
application. The application then looks up the DN/CA pair in its own database.
A valid certificate alone is not enough if that identity is unknown or
suspended.

.. important::

   Use the public HTTPS address supplied by your administrator. The internal
   web server and DIRAC REST daemon are not alternative login endpoints.
   Do not supply certificate-verification headers yourself.

Ordinary users and administrators
---------------------------------

Ordinary registered users can create requests, inspect their own requests and
jobs, and request rescheduling of eligible failed parametric jobs.
Administrators can also see other users' requests, approve requests, mark
results checked or closed, schedule removal, and manage administrator flags.
The users and services API resources are administrator-only.

The administrator flag is stored locally. VOMS synchronization updates
membership-related data but does not automatically grant administrative access.
An operator must bootstrap the first administrator; see
:doc:`operations`.

Your first visit
----------------

#. Open the public URL and select the intended client certificate when prompted.
#. Confirm that the identity shown at the top of the dashboard is yours.
#. Check the monitoring and DIRAC badges before preparing a real request.
#. Select **New Request**, provide a description, and upload the expected
   spreadsheet. Review the preview before submitting.
#. Find the newly created request in the table. It starts in ``Requested``;
   an administrator must approve it before the monitoring daemon submits work.

Continue with :doc:`requests` for the detailed workflow and
:doc:`troubleshooting` if authentication or loading fails.

What updates when
-----------------

There are two separate delays. The dashboard reloads its request table every
two minutes. The monitoring daemon runs a pass and then sleeps for its
configured interval, five minutes by default. A long submission or external
API operation adds to that interval. Refreshing the browser does not force a
monitoring pass.

The DIRAC badge reflects an HTTP check of the configured implementation's
GridPP DIRAC website. It is not proof that a particular job can run, that a
proxy is valid, or that all remote job operations succeed.
