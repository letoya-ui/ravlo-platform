"""Regression tests for retrying Mashvisor's intermittent 500-wrapping-401
errors.

Mashvisor's API intermittently returns:
    {"status": "error", "code": 500, "message": "Request Failed. Status Code: 401"}
with an actual HTTP 500 status, even though the API key and auth header are
confirmed correct (matches their documented x-api-key header, and the same
key succeeds most of the time). This looks like a transient failure on
Mashvisor's own backend rather than a credentials problem, so both Mashvisor
HTTP clients retry once on 500/502/503/504 before giving up.
"""
import json

import requests

from LoanMVP.services.mashvisor_client import MashvisorClient, MashvisorConfig, MashvisorError
import LoanMVP.services.mashvisor_service as mashvisor_service
from LoanMVP.services.mashvisor_service import MashvisorServiceError


def _fake_response(status_code: int, body: dict) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response._content = json.dumps(body).encode("utf-8")
    return response


def _client():
    return MashvisorClient(config=MashvisorConfig(api_key="test-key"))


# ── mashvisor_client.MashvisorClient._get ──

def test_client_get_retries_once_on_500_then_succeeds(monkeypatch):
    client = _client()
    monkeypatch.setattr("LoanMVP.services.mashvisor_client.time.sleep", lambda *_: None)

    responses = [
        _fake_response(500, {"status": "error", "code": 500, "message": "Request Failed. Status Code: 401"}),
        _fake_response(200, {"status": "success", "content": {"id": "123"}}),
    ]
    calls = {"count": 0}

    def fake_get(*args, **kwargs):
        calls["count"] += 1
        return responses[calls["count"] - 1]

    monkeypatch.setattr(client.session, "get", fake_get)

    data = client._get("property", params={"address": "1 Main St"})

    assert calls["count"] == 2
    assert data["content"]["id"] == "123"


def test_client_get_raises_after_exhausting_retries_on_persistent_500(monkeypatch):
    client = _client()
    monkeypatch.setattr("LoanMVP.services.mashvisor_client.time.sleep", lambda *_: None)

    calls = {"count": 0}

    def fake_get(*args, **kwargs):
        calls["count"] += 1
        return _fake_response(500, {"status": "error", "code": 500, "message": "Request Failed. Status Code: 401"})

    monkeypatch.setattr(client.session, "get", fake_get)

    try:
        client._get("property", params={"address": "1 Main St"})
        assert False, "expected MashvisorError"
    except MashvisorError as exc:
        assert "500" in str(exc)

    assert calls["count"] == 2


def test_client_get_does_not_retry_on_non_retryable_status(monkeypatch):
    client = _client()
    monkeypatch.setattr("LoanMVP.services.mashvisor_client.time.sleep", lambda *_: None)

    calls = {"count": 0}

    def fake_get(*args, **kwargs):
        calls["count"] += 1
        return _fake_response(400, {"status": "error", "code": 400, "message": "Bad Request"})

    monkeypatch.setattr(client.session, "get", fake_get)

    try:
        client._get("property", params={"address": "1 Main St"})
        assert False, "expected MashvisorError"
    except MashvisorError:
        pass

    assert calls["count"] == 1


def test_client_get_returns_data_on_409_without_retry(monkeypatch):
    client = _client()
    monkeypatch.setattr("LoanMVP.services.mashvisor_client.time.sleep", lambda *_: None)

    calls = {"count": 0}

    def fake_get(*args, **kwargs):
        calls["count"] += 1
        return _fake_response(409, {"status": "error", "message": "Property already exist", "content": {"id": "456"}})

    monkeypatch.setattr(client.session, "get", fake_get)

    data = client._get("property", params={"address": "1 Main St"})

    assert calls["count"] == 1
    assert data["content"]["id"] == "456"


# ── mashvisor_service._get ──

def test_service_get_retries_once_on_500_then_succeeds(monkeypatch):
    monkeypatch.setattr(mashvisor_service, "MASHVISOR_API_KEY", "test-key")
    monkeypatch.setattr(mashvisor_service.time, "sleep", lambda *_: None)

    responses = [
        _fake_response(500, {"status": "error", "code": 500, "message": "Request Failed. Status Code: 401"}),
        _fake_response(200, {"status": "success", "content": {}}),
    ]
    calls = {"count": 0}

    def fake_get(*args, **kwargs):
        calls["count"] += 1
        return responses[calls["count"] - 1]

    monkeypatch.setattr(mashvisor_service._session, "get", fake_get)

    data = mashvisor_service._get("/v1.1/client/property", params={})

    assert calls["count"] == 2
    assert data["status"] == "success"


def test_service_get_raises_after_exhausting_retries_on_persistent_500(monkeypatch):
    monkeypatch.setattr(mashvisor_service, "MASHVISOR_API_KEY", "test-key")
    monkeypatch.setattr(mashvisor_service.time, "sleep", lambda *_: None)

    calls = {"count": 0}

    def fake_get(*args, **kwargs):
        calls["count"] += 1
        return _fake_response(500, {"status": "error", "code": 500, "message": "Request Failed. Status Code: 401"})

    monkeypatch.setattr(mashvisor_service._session, "get", fake_get)

    try:
        mashvisor_service._get("/v1.1/client/property", params={})
        assert False, "expected MashvisorServiceError"
    except MashvisorServiceError:
        pass

    assert calls["count"] == 2
