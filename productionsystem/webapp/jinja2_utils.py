"""Utilities for Jinja2."""
from __future__ import annotations

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
