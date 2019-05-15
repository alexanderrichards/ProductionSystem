"""Utilities for Jinja2."""
# Py2/3 compatibility layer
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *  # pylint: disable=wildcard-import, unused-wildcard-import, redefined-builtin

import jinja2


def jinja2_filter(filt):
    """
    Create Jinja2 filter.

    Decorator to load a custom filter into Jinja2.
    Args:
        filt (function): A Jinja2 filter function.
    Returns:
        function: The filter function.

    """
    jinja2.filters.FILTERS[filt.__name__] = filt
    return filt
