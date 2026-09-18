"""SQL Models."""
from __future__ import annotations

from importlib import import_module

from productionsystem.config import ConfigSystem

__all__ = ("DiracJobs", "ParametricJobs", "Requests", "Services", "Users")
_LOCAL_MODELS = {"Services", "Users"}
# Dependency order: DiracJobs/Services/Users have no dependencies on the others below; but
# ParametricJobs relies on DiracJobs, and Requests relies on ParametricJobs and Users, so those
# must already be resolved to their classes (not raw modules) by the time they're imported.
_LOAD_ORDER = ("Services", "Users", "DiracJobs", "ParametricJobs", "Requests")


def _load_one(name):
    """Import and return the model class for ``name``."""
    if name in _LOCAL_MODELS:
        return getattr(import_module("%s.%s" % (__name__, name)), name)
    entry_points = ConfigSystem.get_instance().entry_point_map
    return entry_points['dbmodels'][name.lower()].load()


def __getattr__(name):
    """
    Load model classes on demand to avoid recursive entry-point imports.

    Importing a submodule such as ``productionsystem.sql.models.Requests`` (whether via
    ``.load()``, a sibling model's own inter-model import, or a direct
    ``from productionsystem.sql.models.Requests import ...`` statement) causes Python's import
    machinery to set that submodule as an attribute of this package as a side effect of the
    *first* import of the submodule - shadowing the resolved class with the raw module unless
    something explicitly corrects it afterwards. To avoid a "first one wins" race between
    whichever of these submodules happens to get imported first (elsewhere, bypassing this
    lazy loader), resolve *all* of the known models in one dependency-ordered pass the first
    time any single one of them is requested, so every name ends up correctly self-healed to
    its class and no further access falls back to this function.
    """
    if name not in __all__:
        raise AttributeError("module %r has no attribute %r" % (__name__, name))

    for model_name in _LOAD_ORDER:
        globals()[model_name] = _load_one(model_name)

    return globals()[name]
