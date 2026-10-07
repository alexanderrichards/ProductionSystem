"""
Tests for the FastAPI-based webapp services (HTML pages + RESTful API).
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def setup_database(url):
    """
    Point the session registry singleton at a fresh database.
    """
    from productionsystem.sql.registry import SessionRegistry

    if vars(SessionRegistry).get("__instance__") is not None:
        delattr(SessionRegistry, "__instance__")
    SessionRegistry.setup(url)


@pytest.fixture
def app_and_db(tmp_path):
    """
    Build a FastAPI app wired with the real service routers, backed by a fresh sqlite DB.
    """
    from sqlalchemy.orm import make_transient

    from productionsystem.apache_utils import DUMMY_USER, get_dummy_user, get_verified_user
    from productionsystem.sql.models import Requests
    from productionsystem.sql.registry import managed_session
    from productionsystem.webapp.services import HTMLPageServer
    from productionsystem.webapp.services.RESTfulAPI import build_router

    setup_database("sqlite:///" + str(tmp_path / "webapp.db"))

    # DUMMY_USER is a shared module-level singleton (reused by every test in this file and by
    # production mock-mode code). Reset it to a transient state before persisting it into this
    # test's fresh database, otherwise it stays bound to whichever session/engine last saved it.
    make_transient(DUMMY_USER)
    with managed_session() as session:
        session.add(DUMMY_USER)
        session.flush()
        session.add(Requests(requester_id=DUMMY_USER.id, description="a request"))

    app = FastAPI()
    app.include_router(HTMLPageServer().router())
    app.include_router(build_router(), prefix="/api")
    app.dependency_overrides[get_verified_user] = get_dummy_user

    return app, DUMMY_USER


def test_index_page_renders(app_and_db):
    """
    The dashboard page renders successfully for a verified user.
    """
    app, _ = app_and_db
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_requests_list_keeps_enum_names_and_nested_requester(app_and_db):
    """
    The /api/requests endpoint returns enum names and a nested requester object.
    """
    app, user = app_and_db
    client = TestClient(app)
    response = client.get("/api/requests")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["status"] == "Requested"
    assert payload[0]["requester"]["name"] == user.name


def test_requests_post_creates_request(app_and_db):
    """
    POSTing a new request creates a row visible via the list endpoint.
    """
    app, _ = app_and_db
    client = TestClient(app)
    response = client.post("/api/requests", json={"request": {"description": "another request"}})
    assert response.status_code == 200
    response = client.get("/api/requests")
    assert len(response.json()) == 2


def test_requests_put_status_transition(app_and_db):
    """
    PUT can transition a request's status through the allowed states.
    """
    app, _ = app_and_db
    client = TestClient(app)
    response = client.put("/api/requests/1", data={"status": "Approved"})
    assert response.status_code == 200
    response = client.get("/api/requests/1")
    assert response.json()["status"] == "Approved"


def test_requests_delete_marks_for_removal(app_and_db):
    """
    DELETE marks a request as REMOVING rather than deleting outright.
    """
    app, _ = app_and_db
    client = TestClient(app)
    response = client.delete("/api/requests/1")
    assert response.status_code == 200
    response = client.get("/api/requests/1")
    assert response.json()["status"] == "Removing"


def test_services_requires_admin_and_lists(app_and_db):
    """
    The /api/services endpoint is reachable by the (admin) dummy user.
    """
    app, _ = app_and_db
    client = TestClient(app)
    response = client.get("/api/services")
    assert response.status_code == 200
    assert response.json() == []


def test_users_list_returns_dummy_user(app_and_db):
    """
    The /api/users endpoint returns the seeded dummy user.
    """
    app, user = app_and_db
    client = TestClient(app)
    response = client.get("/api/users")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["name"] == user.name
