"""JSON Utilities Module."""

import json
import cherrypy
from .SQLTableBase import SQLTableBase


class JSONTableEncoder(json.JSONEncoder):
    """JSON encoder for SQLAlchemy tables."""

    def default(self, obj):
        """Override base default method."""
        if isinstance(obj, SQLTableBase):
            return obj.jsonable_dict()
        return json.JSONEncoder.default(self, obj)


def json_cherrypy_handler(*args, **kwargs):
    """Handle JSON encoding of response."""
    value = cherrypy.serving.request._json_inner_handler(*args, **kwargs)
    return json.dumps(value, cls=JSONTableEncoder)
