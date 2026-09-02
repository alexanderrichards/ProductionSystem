"""SQL Models."""
from __future__ import annotations

from importlib import import_module

from productionsystem.config import ConfigSystem

__all__ = ("DiracJobs", "ParametricJobs", "Requests", "Services", "Users")
_LOCAL_MODELS = {"Services", "Users"}


def __getattr__(name):
    """Load model classes on demand to avoid recursive entry-point imports."""
    if name in _LOCAL_MODELS:
        model = getattr(import_module("%s.%s" % (__name__, name)), name)
    elif name in __all__:
        entry_points = ConfigSystem.get_instance().entry_point_map
        model = entry_points['dbmodels'][name.lower()].load()
    else:
        raise AttributeError("module %r has no attribute %r" % (__name__, name))

    globals()[name] = model
    return model
