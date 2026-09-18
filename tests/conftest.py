"""Define necessary setup fixtures."""
import pytest
from productionsystem.cli import load_entry_points
from productionsystem.config import ConfigSystem


@pytest.fixture(scope="session", autouse=True)
def config():
    """Set up the config entrypoint map."""
    config_instance = ConfigSystem.setup(None)  # pylint: disable=no-member
    # Use the importlib.metadata-based entry point map (same as production code paths), rather
    # than pkg_resources.get_entry_map(...). pkg_resources' EntryPoint.load() internally calls
    # self.require(), which resolves the *entire* package's install_requires (not just what's
    # needed for the entry point being loaded) and raises DistributionNotFound if an unrelated
    # dependency (e.g. suds-py3) isn't installed in the dev environment. That failure happens
    # after the target submodule has already been imported, permanently leaving
    # productionsystem.sql.models.<Name> bound to the raw submodule instead of self-healing to
    # the resolved class.
    entry_point_map, _projects = load_entry_points()
    config_instance.entry_point_map = entry_point_map
    return config_instance


@pytest.fixture(autouse=True)
def _reset_lazy_sql_models():
    """
    Undo any package-attribute pollution left over from a previous test before each test runs.

    Some code (production or test) imports a productionsystem.sql.models submodule (e.g. via
    ``entry_point.load()`` or a direct dotted import) without going through the package's own
    lazy-loading ``__getattr__``. Since Python auto-sets the submodule as a package attribute the
    first time it's imported, this can leave ``productionsystem.sql.models.<Name>`` bound to the
    raw module rather than the resolved class for the remainder of the test process. Clearing
    these attributes before each test forces the lazy loader to run (and self-heal) again.
    """
    import productionsystem.sql.models as sql_models

    for name in ("Services", "Users", "DiracJobs", "ParametricJobs", "Requests"):
        sql_models.__dict__.pop(name, None)
