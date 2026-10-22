"""
JSON Utilities Module.

Adapt mapped table instances to standard-library JSON encoding using their
``jsonable_dict`` representation.
"""
from __future__ import annotations

import json

from .SQLTableBase import SQLTableBase


class JSONTableEncoder(json.JSONEncoder):
    """
    JSON encoder for SQLAlchemy tables.

    Serialize ``SQLTableBase`` instances through their JSON-ready mappings.
    Delegate other unsupported objects to the standard encoder, which raises
    ``TypeError`` when no default conversion exists.
    """
    # pylint: disable=method-hidden
    def default(self, obj):
        """
        Override base default method.

        Args:
            obj: Object being serialized by ``json.dumps``.

        Returns:
            dict | object: JSON-ready table mapping, or the base encoder fallback result.
        """
        if isinstance(obj, SQLTableBase):
            return obj.jsonable_dict()
        return json.JSONEncoder.default(self, obj)
