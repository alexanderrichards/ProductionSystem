"""JSON Utilities Module."""

import json
from enum import Enum
from datetime import datetime
from .models import SQLTableBase


class JSONTableEncoder(json.JSONEncoder):
    """JSON encoder for SQLAlchemy tables."""

    def default(self, obj):
        """Override base default method."""
        if isinstance(obj, Enum):
            return obj.name
        if isinstance(obj, SQLTableBase):
            return dict(obj, status=obj.status.name)
        if isinstance(obj, datetime):
            return obj.isoformat(' ')
        return super(json.JSONEncoder, self).default(obj)
