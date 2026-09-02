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


def test_service_queries_return_mapped_entities(tmp_path):
    """ORM helpers return model instances rather than SQLAlchemy rows."""
    from productionsystem.sql.enums import ServiceStatus
    from productionsystem.sql.models import Services
    from productionsystem.sql.registry import SessionRegistry

    database = "sqlite:///" + str(tmp_path / "services.db")
    SessionRegistry.setup(database)
    service = Services(name="monitoringd", status=ServiceStatus.UP)
    service.add()

    services = Services.get_services()
    assert services[0].name == "monitoringd"
    assert Services.get_services(service_name="monitoringd").name == "monitoringd"
