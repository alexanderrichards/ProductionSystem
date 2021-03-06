"""JSON Utilities Module."""
# Py2/3 compatibility layer
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *  # pylint: disable=wildcard-import, unused-wildcard-import, redefined-builtin

import json
import cherrypy
from .SQLTableBase import SQLTableBase


class JSONTableEncoder(json.JSONEncoder):
    """JSON encoder for SQLAlchemy tables."""

    # pylint: disable=method-hidden
    def default(self, obj):
        """Override base default method."""
        if isinstance(obj, SQLTableBase):
            return obj.jsonable_dict()
        return json.JSONEncoder.default(self, obj)


def json_cherrypy_handler(*args, **kwargs):
    """Handle JSON encoding of response."""
    value = cherrypy.serving.request._json_inner_handler(*args, **kwargs)
    return json.dumps(value, cls=JSONTableEncoder)
