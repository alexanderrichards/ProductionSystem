"""Regression tests for HTTPX arguments and X509 configuration."""

import importlib
import json
import ssl
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
import pytest

from productionsystem.api import JSI
from productionsystem.http_utils import create_ssl_context
from productionsystem.suds_utils import HttpCertAuthenticated


@pytest.mark.parametrize("verify", [True, False])
def test_ssl_verification_flags(verify):
    context = create_ssl_context(verify=verify)
    assert context.check_hostname is verify
    assert context.verify_mode == (ssl.CERT_REQUIRED if verify else ssl.CERT_NONE)


@pytest.mark.parametrize("directory", [False, True])
def test_custom_ca_paths(tmp_path, directory):
    path = tmp_path if directory else tmp_path / "ca.pem"
    with patch("productionsystem.http_utils.ssl.create_default_context") as factory:
        assert create_ssl_context(verify=str(path)) is factory.return_value
    factory.assert_called_once_with(**{"capath" if directory else "cafile": str(path)})


@pytest.mark.parametrize("verify", [True, False])
@pytest.mark.parametrize("cert", ["combined.pem", ("cert.pem", "key.pem"), None])
def test_client_certificate_loading(cert, verify):
    with patch.object(ssl.SSLContext, "load_cert_chain", autospec=True) as load:
        create_ssl_context(cert, verify)
    if cert is None:
        load.assert_not_called()
    else:
        load.assert_called_once_with(*(cert if isinstance(cert, tuple) else (cert,)))


def test_invalid_tls_files_are_not_silently_ignored(tmp_path):
    with pytest.raises(OSError):
        create_ssl_context(cert=str(tmp_path / "missing.pem"), verify=False)
    with pytest.raises(OSError):
        create_ssl_context(verify=str(tmp_path / "missing-ca.pem"))


@pytest.fixture
def http_transport(monkeypatch):
    """Replace only the network layer, retaining real HTTPX argument validation."""
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.path.endswith("/parametricjobs"):
            data = [{"id": 2}]
        elif request.url.path == "/api/requests/1":
            data = {"id": 1}
        else:
            data = []
        return httpx.Response(200, json=data)

    monkeypatch.setattr("httpx._client.HTTPTransport", lambda **kwargs: httpx.MockTransport(respond))
    return requests


def test_jsi_gets_request_and_parametric_jobs(http_transport):
    client = JSI("https://example.test")
    assert client.get_requests() == []
    assert client.get_requests(1) == [{"id": 1, "parametricjobs": [{"id": 2}]}]
    assert [request.url.path for request in http_transport] == [
        "/api/requests", "/api/requests/1", "/api/requests/1/parametricjobs",
    ]


@pytest.mark.parametrize(
    ("method", "args", "verb", "body"),
    [
        ("create_request", ({"description": "test"},), "POST", {"request": {"description": "test"}}),
        ("modify_request_status", (1, "approved"), "PUT", "status=Approved"),
        ("approve_request", (1,), "PUT", "status=Approved"),
        ("mark_checked", (1,), "PUT", "status=Checked"),
        ("mark_closed", (1,), "PUT", "status=Closed"),
        ("delete_request", (1,), "DELETE", ""),
    ],
)
def test_jsi_write_methods_use_valid_httpx_arguments(http_transport, method, args, verb, body):
    response = getattr(JSI("https://example.test"), method)(*args)
    assert response.status_code == 200
    request, = http_transport
    assert request.method == verb
    if verb == "POST":
        assert json.loads(request.content) == body
    else:
        assert request.content.decode() == body
        if verb == "PUT":
            assert request.headers["content-type"] == "application/x-www-form-urlencoded"
    assert response.is_closed


def test_jsi_configures_certificate_on_ssl_context(http_transport):
    with patch.object(ssl.SSLContext, "load_cert_chain", autospec=True) as load:
        JSI("https://example.test", cert=("cert.pem", "key.pem")).get_requests()
    load.assert_called_once_with("cert.pem", "key.pem")


def test_suds_transport_uses_valid_httpx_arguments(http_transport):
    transport = HttpCertAuthenticated(None, verify=False)
    try:
        request = SimpleNamespace(
            url="https://example.test/soap",
            message=b"<soap>payload</soap>",
            headers={"Content-Type": "text/xml"},
        )
        with transport.open(request) as body:
            assert body.read() == b"[]"
        reply = transport.send(request)
        assert reply.code == 200
        assert reply.message == b"[]"
        assert http_transport[-1].content == request.message
        assert http_transport[-1].headers["content-type"] == "text/xml"
    finally:
        transport._client.close()


def test_monitoring_health_check_uses_valid_httpx_arguments(http_transport):
    pytest.importorskip("fcntl", reason="The monitoring daemon requires POSIX daemonize support")
    module = importlib.import_module("productionsystem.monitoring.MonitoringDaemon")
    daemon = object.__new__(module.MonitoringDaemon)
    daemon.cert = ("cert.pem", "key.pem")
    daemon.verify = False
    daemon.logger = Mock()
    services = {
        name: SimpleNamespace(name=name, status=None, update=Mock())
        for name in ("DIRAC", "monitoringd")
    }
    with patch.object(module.Services, "get_services", return_value=list(services.values())), \
            patch.object(ssl.SSLContext, "load_cert_chain", autospec=True) as load:
        daemon.check_services()
    load.assert_called_once_with("cert.pem", "key.pem")
    assert services["DIRAC"].status == module.ServiceStatus.UP
    assert services["monitoringd"].status == module.ServiceStatus.UP
    assert str(http_transport[0].url) == "https://dirac.gridpp.ac.uk/DIRAC/"


def test_git_listing_uses_valid_httpx_arguments(http_transport):
    from productionsystem.webapp.services.GitListing import GitListingBase

    listing = GitListingBase(access_token="test-token")
    assert listing._call_api("https://example.test/tags", params={"page": 2}) == []
    request, = http_transport
    assert request.url.params["page"] == "2"
    assert request.headers["authorization"] == "token test-token"


@pytest.mark.parametrize("method", ["GET", "POST", "DELETE"])
def test_dirac_rest_uses_valid_httpx_arguments(http_transport, method):
    from productionsystem.monitoring.diracrest.DiracRESTClient import DiracAPIClient, REQUEST_TIMEOUT

    client = DiracAPIClient()
    try:
        assert client._request(method, "/jobs", {"job_ids": {1, 2}}) == []
        request, = http_transport
        assert request.method == method
        assert sorted(json.loads(request.content)["job_ids"]) == [1, 2]
        assert request.extensions["timeout"]["read"] == REQUEST_TIMEOUT
    finally:
        client.close()
