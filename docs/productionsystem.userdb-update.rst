productionsystem.userdb\-update module
======================================

Synchronizes the local user table with VOMS using SQLAlchemy 2 ORM statements.
Users are identified by their DN and CA pair, so a CA change adds the new
identity; an absent old identity with retained history is suspended rather
than deleted. Existing identities retain their administrator flag while their
email address and suspended status are synchronized. See
:doc:`user/operations` for the complete reconciliation rules.

.. literalinclude:: ../scripts/userdb-update.py
   :language: python
   :caption: scripts/userdb-update.py
