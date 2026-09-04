"""Tests for the Typer command-line applications."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from typer.testing import CliRunner

SCRIPTS = Path(__file__).parents[1] / "scripts"


def load_script(name):
    """Load a hyphenated script as a Python module."""
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), SCRIPTS / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "script_name",
    ("dirac-daemon.py", "monitoring-daemon.py", "webapp-daemon.py"),
)
def test_daemon_help_lists_start_and_stop_commands(script_name):
    """Daemon Typer applications expose their lifecycle commands."""
    result = CliRunner().invoke(load_script(script_name).app, ["--help"])
    assert result.exit_code == 0
    assert "start" in result.output
    assert "stop" in result.output


def test_userdb_help_lists_options():
    """The user database updater remains a single-command application."""
    result = CliRunner().invoke(load_script("userdb-update.py").app, ["--help"])
    assert result.exit_code == 0
    assert "--voms" in result.output
    assert "--trusted-cas" in result.output


def test_config_file_values_override_command_defaults(tmp_path):
    """Config file values replace Typer defaults."""
    module = load_script("webapp-daemon.py")
    config = tmp_path / "productionsystem.conf"
    config.write_text(
        '[webapp]\ndburl="sqlite:///from-config.db"\nsocket_port=9999\n',
        encoding="utf-8",
    )
    seen = {}

    def fake_start(args, *, logger):
        seen["dburl"] = args.dburl
        seen["socket_port"] = args.socket_port

    module.start = fake_start
    result = CliRunner().invoke(
        module.app,
        ["start", "--config", str(config), "--debug-mode"],
    )
    assert result.exit_code == 0
    assert seen == {"dburl": "sqlite:///from-config.db", "socket_port": 9999}


def test_command_line_values_override_config_file(tmp_path):
    """Explicit command-line options keep precedence over config files."""
    module = load_script("webapp-daemon.py")
    config = tmp_path / "productionsystem.conf"
    config.write_text(
        '[webapp]\ndburl="sqlite:///from-config.db"\n',
        encoding="utf-8",
    )
    seen = {}

    def fake_start(args, *, logger):
        seen["dburl"] = args.dburl

    module.start = fake_start
    result = CliRunner().invoke(
        module.app,
        [
            "start",
            "--config",
            str(config),
            "--debug-mode",
            "--dburl",
            "sqlite:///from-cli.db",
        ],
    )
    assert result.exit_code == 0
    assert seen == {"dburl": "sqlite:///from-cli.db"}


def test_model_entry_points_load_without_duplicate_mappers():
    """The daemon's real model entry points load with SQLAlchemy 2."""
    from sqlalchemy.orm import configure_mappers

    from productionsystem.cli import load_entry_points
    from productionsystem.config import ConfigSystem

    entry_points, _ = load_entry_points()
    config = ConfigSystem.get_instance()
    config._config["Core"]["entry_point_map"] = entry_points  # pylint: disable=protected-access
    models = entry_points["dbmodels"]
    assert models["diracjobs"].load().__name__ == "DiracJobs"
    assert models["parametricjobs"].load().__name__ == "ParametricJobs"
    assert models["requests"].load().__name__ == "Requests"
    configure_mappers()


def setup_database(url):
    """Point the session registry singleton at a fresh database."""
    from productionsystem.sql.registry import SessionRegistry

    if vars(SessionRegistry).get("__instance__") is not None:
        delattr(SessionRegistry, "__instance__")
    SessionRegistry.setup(url)


def test_service_queries_return_mapped_entities(tmp_path):
    """ORM helpers return model instances rather than SQLAlchemy rows."""
    from productionsystem.sql.enums import ServiceStatus
    from productionsystem.sql.models import Services

    database = "sqlite:///" + str(tmp_path / "services.db")
    setup_database(database)
    service = Services(name="monitoringd", status=ServiceStatus.UP)
    service.add()

    services = Services.get_services()
    assert services[0].name == "monitoringd"
    assert Services.get_services(service_name="monitoringd").name == "monitoringd"


def test_request_json_keeps_enum_names_and_nested_requester(tmp_path):
    """Serialised requests expose the requester object and enum names."""
    import json

    from productionsystem.cli import load_entry_points
    from productionsystem.config import ConfigSystem
    from productionsystem.sql.JSONTableEncoder import JSONTableEncoder
    from productionsystem.sql.registry import managed_session
    from productionsystem.sql.models import Users

    entry_points, _ = load_entry_points()
    config = ConfigSystem.get_instance()
    config._config["Core"]["entry_point_map"] = entry_points  # pylint: disable=protected-access
    Requests = entry_points["dbmodels"]["requests"].load()

    setup_database("sqlite:///" + str(tmp_path / "requests.db"))
    with managed_session() as session:
        user = Users(dn="/C=XX/OU=test/CN=Test User", ca="/C=XX/CN=Test CA",
                     email="test@example.com", suspended=False, admin=True)
        session.add(user)
        session.flush()
        session.add(Requests(requester_id=user.id, description="a request"))

    request = Requests.get(load_user=True)[0]
    payload = json.loads(json.dumps(request, cls=JSONTableEncoder))

    assert payload["requester"]["name"] == "Test User"
    assert payload["status"] == "Requested"
