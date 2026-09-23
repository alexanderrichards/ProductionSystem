"""JSON Utilities Module."""
from __future__ import annotations

import json

from .SQLTableBase import SQLTableBase


class JSONTableEncoder(json.JSONEncoder):
    """JSON encoder for SQLAlchemy tables."""

    # pylint: disable=method-hidden
    def default(self, obj):
        """Override base default method."""
        if isinstance(obj, SQLTableBase):
            return obj.jsonable_dict()
        return json.JSONEncoder.default(self, obj)
