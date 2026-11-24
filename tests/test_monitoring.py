"""Test background request operations without starting a daemon process."""
from __future__ import annotations

import importlib
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Event, get_ident
from unittest.mock import Mock

import pytest
from sqlalchemy.orm.exc import NoResultFound

from productionsystem.sql.enums import LocalStatus


@pytest.fixture
def monitoring(config):
    """Load the daemon after model extension discovery has been initialized."""
    return importlib.import_module("productionsystem.monitoring.MonitoringDaemon")


@pytest.fixture
def daemon(monkeypatch, monitoring):
    """Create a monitor with a real worker and mocked external dependencies."""
    monkeypatch.setattr(monitoring.Daemonize, "__init__", lambda self, **kwargs: None)
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(monitoring, "dirac_api_client", lambda: client)
    instance = monitoring.MonitoringDaemon("sqlite://", 1, None)
    instance.logger = logging.getLogger(__name__)
    with ThreadPoolExecutor(max_workers=1) as executor:
        instance._request_executor = executor
        yield instance
    instance._reap_request_operations()


@pytest.mark.parametrize("status", [LocalStatus.APPROVED, LocalStatus.REMOVING])
def test_slow_operations_do_not_block_monitoring(daemon, monkeypatch, monitoring, status):
    """Monitor other requests on repeated passes while an operation is blocked."""
    request = Mock(id=1, status=status)
    running = Mock(id=2, status=LocalStatus.RUNNING)
    started, release = Event(), Event()
    worker_threads = []

    def block():
        worker_threads.append(get_ident())
        started.set()
        assert release.wait(5), "Test did not release the background operation"

    operation = request.submit if status == LocalStatus.APPROVED else request.remove
    operation.side_effect = block

    def get_requests(**kwargs):
        if "request_id" in kwargs:
            return request
        return [request, running]

    monkeypatch.setattr(monitoring.Requests, "get", get_requests)
    monkeypatch.setattr(monitoring.Requests, "get_reschedules", lambda: [])
    try:
        daemon.monitor_requests()
        assert started.wait(5)
        daemon.monitor_requests()
        assert running.monitor.call_count == 2
        assert running.update.call_count == 2
        request.monitor.assert_not_called()
        assert operation.call_count == 1
        assert len(worker_threads) == 1
        assert worker_threads[0] != get_ident()
        assert len(daemon._request_operations) == 1
    finally:
        release.set()
        daemon._request_operations[1].result(timeout=5)

    if status == LocalStatus.APPROVED:
        assert request.status == LocalStatus.SUBMITTING
        assert request.update.call_count == 3
        request.monitor.assert_called_once()
    else:
        request.update.assert_not_called()
        request.monitor.assert_not_called()
    daemon._reap_request_operations()
    assert not daemon._request_operations


def test_worker_reloads_queued_request_state(daemon, monkeypatch, monitoring):
    """A request marked for removal while queued is deleted, not submitted."""
    queued = Mock(id=1, status=LocalStatus.APPROVED)
    current = Mock(id=1, status=LocalStatus.REMOVING)
    started, release = Event(), Event()

    def block_worker():
        started.set()
        assert release.wait(5)

    blocker = daemon._request_executor.submit(block_worker)
    get_requests = Mock(side_effect=lambda **kwargs: current if "request_id" in kwargs else [queued])
    monkeypatch.setattr(monitoring.Requests, "get", get_requests)
    monkeypatch.setattr(monitoring.Requests, "get_reschedules", lambda: [])
    try:
        assert started.wait(5)
        daemon.monitor_requests()
        assert not daemon._request_operations[1].running()
    finally:
        release.set()
        blocker.result(timeout=5)
        daemon._request_operations[1].result(timeout=5)
    current.remove.assert_called_once()
    queued.submit.assert_not_called()
    current.submit.assert_not_called()
    get_requests.assert_any_call(request_id=1, load_parametricjobs=True)


def test_background_failure_is_logged_and_other_work_continues(daemon, monkeypatch, monitoring, caplog):
    """A worker exception is reported and does not prevent later operations."""
    broken = Mock(id=1, status=LocalStatus.REMOVING)
    broken.remove.side_effect = RuntimeError("deletion failed")
    other = Mock(id=2, status=LocalStatus.REMOVING)
    monkeypatch.setattr(monitoring.Requests, "get", lambda **kwargs: {1: broken, 2: other}[kwargs["request_id"]])
    daemon._request_operations[1] = daemon._request_executor.submit(daemon._process_request, 1)
    daemon._request_operations[2] = daemon._request_executor.submit(daemon._process_request, 2)
    daemon._request_operations[2].result(timeout=5)
    daemon._reap_request_operations()
    assert "Unhandled exception while processing request 1" in caplog.text
    assert "deletion failed" in caplog.text
    other.remove.assert_called_once()
    assert not daemon._request_operations


def test_disappearing_request_is_logged(daemon, monkeypatch, monitoring, caplog):
    """A request deleted before its worker starts does not crash processing."""
    monkeypatch.setattr(monitoring.Requests, "get", Mock(side_effect=NoResultFound))
    daemon._process_request(1)
    assert "Request 1 disappeared before background processing" in caplog.text


def test_worker_ignores_requests_no_longer_approved_or_removing(daemon, monkeypatch, monitoring):
    """Queued work respects a changed lifecycle state."""
    request = Mock(id=1, status=LocalStatus.RUNNING)
    monkeypatch.setattr(monitoring.Requests, "get", Mock(return_value=request))
    daemon._process_request(1)
    request.submit.assert_not_called()
    request.remove.assert_not_called()
    request.update.assert_not_called()


@pytest.mark.parametrize("status", [LocalStatus.APPROVED, LocalStatus.REMOVING])
def test_worker_persists_operations_with_independent_sessions(daemon, monkeypatch, monitoring, tmp_path, status):
    """Exercise background database reads and writes against file-backed SQLite."""
    from productionsystem.sql.models import Users
    from productionsystem.sql.registry import SessionRegistry, managed_session

    monkeypatch.setattr(SessionRegistry, "__instance__", None, raising=False)
    registry = SessionRegistry.setup("sqlite:///" + str(tmp_path / "monitoring.db"))
    try:
        with managed_session() as session:
            user = Users(dn="test-dn", ca="test-ca", email="test@example.com",
                         suspended=False, admin=True)
            session.add(user)
            session.flush()
            request = monitoring.Requests(requester_id=user.id)
            session.add(request)
        request.status = status
        request.update()

        worker_requests = []

        def submit(current):
            worker_requests.append(current)
            current.log += "submitted in worker\n"

        def monitor(current):
            current.status = LocalStatus.SUBMITTED

        monkeypatch.setattr(monitoring.Requests, "submit", submit)
        monkeypatch.setattr(monitoring.Requests, "monitor", monitor)
        daemon.monitor_requests()
        daemon._request_operations[request.id].result(timeout=5)

        if status == LocalStatus.APPROVED:
            persisted = monitoring.Requests.get(request_id=request.id, load_parametricjobs=True)
            assert persisted.status == LocalStatus.SUBMITTED
            assert "submitted in worker" in persisted.log
            assert worker_requests[0] is not request
        else:
            with pytest.raises(NoResultFound):
                monitoring.Requests.get(request_id=request.id)
    finally:
        registry.engine.dispose()


def test_main_drains_worker_on_shutdown(daemon, monkeypatch, monitoring, caplog):
    """Loop shutdown cancels queued work, drains active work, and logs failures."""
    monkeypatch.setattr(monitoring.SessionRegistry, "setup", Mock())
    monkeypatch.setattr(daemon, "check_services", Mock())
    started, release, finished = Event(), Event(), Event()
    queued_work = Mock()
    queued = []

    def work():
        started.set()
        assert release.wait(5)
        finished.set()
        raise RuntimeError("worker failed")

    def monitor():
        daemon._request_operations[1] = daemon._request_executor.submit(work)
        assert started.wait(5)
        operation = daemon._request_executor.submit(queued_work)
        operation.add_done_callback(lambda future: release.set() if future.cancelled() else None)
        daemon._request_operations[2] = operation
        queued.append(operation)
        raise KeyboardInterrupt

    monkeypatch.setattr(daemon, "monitor_requests", monitor)
    try:
        daemon.main()
    finally:
        release.set()
    assert finished.is_set()
    assert queued[0].cancelled()
    queued_work.assert_not_called()
    assert "worker failed" in caplog.text
    assert not daemon._request_operations
    with pytest.raises(RuntimeError, match="shutdown"):
        daemon._request_executor.submit(lambda: None)
