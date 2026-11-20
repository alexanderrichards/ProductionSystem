Data model, sessions, and state
===============================

Database relationships
-----------------------

.. code-block:: text

   Users
     |-- Requests
     |     `-- ParametricJobs (request_id, id)
     |              `-- DiracJobs (external id)
     `-- requester_id references on all job levels

   Services (independent named health records)

``Requests.id`` is a production-system primary key.
``ParametricJobs`` uses a composite primary key of request ID and local job ID.
``DiracJobs.id`` is an external DIRAC identifier and has a composite foreign
key to its parent group. Never treat a local parametric-job ID as globally
unique without the request ID.

Requests own parametric jobs with ``all, delete-orphan`` cascading, and groups
own DIRAC rows with the same cascading policy. These cascades remove local
records. A separate ``Session.persistent_to_deleted`` listener detects deleted
parametric-job groups and invokes the DIRAC kill/delete helper.
This is an external side effect during ORM deletion, not a transactional
guarantee that remote cleanup succeeds or rolls back with the database.

The ORM models store a ``classtype`` discriminator for polymorphic request/job
extensions. Built-in user, service, and DIRAC-job models are not replaceable
through the lazy model resolver. See :doc:`extensions` for extension names.

Initialize before importing models
-----------------------------------

The package-level model resolver consults the configuration's entry-point map.
Custom scripts must initialize that map before importing models from
``productionsystem.sql.models``:

.. code-block:: python

   from productionsystem.cli import load_entry_points
   from productionsystem.config import ConfigSystem

   config = ConfigSystem.setup(None)
   config.entry_point_map = load_entry_points()[0]

   from productionsystem.sql.models import Users
   from productionsystem.sql.registry import SessionRegistry, managed_session

   SessionRegistry.setup("sqlite:///:memory:")
   with managed_session() as session:
       session.add(Users(
           dn="/C=EXAMPLE/CN=Development User",
           ca="/C=EXAMPLE/CN=Development CA",
           email="developer@example.org",
           suspended=False,
           admin=False,
       ))

This example is a fresh-process development setup, not a production
administrator bootstrap. ``setup`` is intentionally one-time: repeated setup
on an existing singleton raises ``InstantiationError``. Production code should
access an initialized registry rather than deleting its singleton state.

The lazy package loader resolves all known model names in dependency order.
Direct dotted module imports can temporarily assign submodules to package
attributes with the same names as model classes. Preserve the existing
resolver's self-healing behavior; import-order tests are important when
changing this area.

Transaction ownership
----------------------

``SessionRegistry`` creates an engine with connection pre-ping and creates
missing mapped tables. Its session factory uses ``expire_on_commit=False``.
``managed_session``:

#. Creates a new session.
#. Yields it to the caller.
#. Commits if the body succeeds.
#. Logs, rolls back, and re-raises if the body or commit fails.
#. Closes the session in all cases.

Helpers such as ``Requests.update`` merge an instance in their own managed
transaction. Several helper calls are not automatically one transaction.
When an operation needs atomic changes, perform them inside one explicitly
owned session and test the failure path.

Deletion tests must account for the session event's outbound DIRAC operations.
Mock the private API boundary when testing local cascades, and test cleanup
failure/reconciliation separately. A database rollback cannot undo an external
job cancellation that already succeeded.

Returned ORM instances can be detached. Only attributes loaded before session
close are reliably available. Request queries can eager-load requesters,
parametric jobs, and DIRAC jobs through their flags. Do not let a response
schema or template trigger an unexpected lazy load after the session closes.
The dictionary-style iterable base skips inaccessible detached attributes,
which can affect JSON output shape.

Creation and response schemas
------------------------------

Pydantic creation schemas describe accepted request/group fields separately
from mapped table columns. The built-in ``RequestCreate`` contains description
and a list of ``ParametricJobCreate`` objects; the latter contains priority and
site. Creation assigns the requester from the verified identity rather than
trusting a submitted user ID.

Response schemas use ``from_attributes=True`` and frozen fields to represent
ORM state. They expose status names, nested requester data, counters, logs,
and timestamps without making those fields writable through creation.
Adding an ORM column alone does not automatically add an API input or output
field. Review all three surfaces together:

* Mapped storage and database constraints.
* Creation/response schemas and their serializers.
* Templates, spreadsheet preparation, and browser expectations.

The default Pydantic models do not configure rejection of every unknown field.
Avoid relying on extra input being preserved or on client preview enforcing
server validation.

Timestamp/status serialization is explicit in the Pydantic models.
Request and parametric-job serializers normalize datetimes to UTC, treating
naive database values as UTC. ``JSONTableEncoder`` uses the iterable base's
conversion, including capitalized enum names and ISO-like timestamps. Verify
both paths when changing presentation contracts.

Status reduction
-----------------

``DiracStatus.local_status`` uses the explicit ``STATUS_MAP``.
Examples that matter to monitoring:

* ``DONE`` maps to local ``COMPLETED``.
* DIRAC ``COMPLETED`` and ``COMPLETING`` map to local ``RUNNING``.
* ``FAILED`` and ``STALLED`` map to local ``FAILED``.
* Received/queued/waiting/checking/matched states map to ``SUBMITTED``.

Groups count local states and take the maximum enum value for their overall
state. Requests similarly take the maximum of child group states. Numeric
ordering is therefore behavior, not merely an implementation detail.
Do not renumber enum values casually or replace the reduction without tests
for mixed success/failure/running combinations.

The SQLAlchemy status-set listeners append transition logs when operating on
attached instances. Detached mutation and later merge can affect when an event
is observed. Test persisted logs, not only in-memory attribute assignments.

Schema evolution
-----------------

There is no included migration framework. ``create_all`` does not add or
transform existing columns safely. For model changes:

#. Specify the intended old-to-new schema and data transformation.
#. Test it on a copy, including retained user history and composite foreign keys.
#. Plan coordinated application/extension deployment and backups.
#. Document rollback compatibility and any irreversible data changes.

Do not change production tables merely by deleting and recreating a database.
