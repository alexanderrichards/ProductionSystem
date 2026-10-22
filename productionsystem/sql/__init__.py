"""
ProductionSystem SQL subpackage.

Expose ``managed_session`` for transactional database access. Sibling modules
define the session registry, declarative base, status enums, and mapped models.
"""
from __future__ import annotations

from .registry import managed_session

__all__ = ("managed_session",)
