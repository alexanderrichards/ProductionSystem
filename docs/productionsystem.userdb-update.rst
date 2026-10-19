productionsystem.userdb\-update module
======================================

Synchronizes the local user table with VOMS using SQLAlchemy 2 ORM statements.
Users are identified by their DN and CA pair, so a CA change adds the new
identity and removes the old one. Existing identities retain their administrator
flag while their email address and suspended status are synchronized.

.. automodule:: productionsystem.userdb-update
    :members:
    :undoc-members:
    :show-inheritance:
