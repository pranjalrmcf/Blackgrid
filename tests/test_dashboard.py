"""Browser session scope, origin protections, expiry and safe live projections."""
import json
import pytest
from fastapi.testclient import TestClient
from blackgrid.operations.api import create_app
from blackgrid.operations.dashboard import Sessions, COOKIE, benchmark_status, LiveView
from tests.test_monitoring import OPS
from tests.test_api import headers
from tests.test_deployment import settings

BASE = "/api/v1/dashboard"
ORIGIN = {"Origin": "https://127.0.0.1"}


def test_dashboard_public_assets_but_private_data_and_scoped_secure_cookie(settings, capsys):
    with TestClient(create_app(settings, OPS), base_url="https://127.0.0.1") as client:
        page = client.get(BASE)
        assert page.status_code == 200 and "LIVE SYSTEM VIEW" in page.text
        assert "script-src 'self'" in page.headers["content-security-policy"]
        assert "unsafe-inline" not in page.headers["content-security-policy"]
        assert client.get(BASE+"/assets/app.js").status_code == 200
        assert client.get(BASE+"/assets/clients.json").status_code == 404
        assert client.get(BASE+"/data").status_code == 401
        assert client.post(BASE+"/session", json={}, headers=headers()).status_code == 403
        assert client.post(BASE+"/session", json={}, headers=headers("bob")|ORIGIN).status_code == 403
        reply = client.post(BASE+"/session", json={}, headers=headers()|ORIGIN)
        assert reply.status_code == 200
        cookie = reply.headers["set-cookie"]
        assert all(s in cookie for s in ("HttpOnly", "Secure", "SameSite=strict", "Path=/api/v1/dashboard", "Max-Age=900"))
        secret = client.cookies.get(COOKIE)
        assert secret not in reply.text and secret not in capsys.readouterr().out
        data = client.get(BASE+"/data").json()
        assert data["refresh_seconds"] == 5 and len(data["history"]) == 1
        assert data["history"][0]["requests_per_second"] is None
        assert client.get("/api/v1/monitoring.json").status_code == 401
        assert client.post("/api/v1/jobs", json={}).status_code == 401
        assert client.post(BASE+"/logout", json={}, headers={"Origin":"https://foreign.example"}).status_code == 403
        assert client.post(BASE+"/logout", json={}, headers=ORIGIN).status_code == 200
        assert client.get(BASE+"/data").status_code == 401


def test_dashboard_session_expiry_capacity_and_restart_invalidation():
    now = [0.]
    sessions = Sessions(clock=lambda:now[0])
    token = sessions.issue("alice")
    assert sessions.owner(token) == "alice"
    assert sessions.owner("wrong") is None
    assert Sessions().owner(token) is None
    for _ in range(3): assert sessions.issue("alice")
    assert sessions.issue("alice") is None
    now[0] = 901
    assert sessions.owner(token) is None and sessions.issue("alice")
    assert token not in sessions.entries


def test_browser_origin_exception_does_not_relax_existing_api(settings):
    with TestClient(create_app(settings, OPS), base_url="https://127.0.0.1") as client:
        assert client.post("/api/v1/jobs", json={}, headers=headers()|ORIGIN).status_code == 403
        assert client.post(BASE+"/session", json={}, headers=headers()|{"Origin":"null"}).status_code == 403
        assert client.post(BASE+"/session", json={}, headers=headers()|{"Origin":"https://127.0.0.1:9999"}).status_code == 403
        assert client.get("/api/v1/benchmark/identity", headers=headers()).status_code == 404


def test_benchmark_dashboard_projection_ignores_private_fields_and_rejects_bad_numbers(tmp_path):
    raw = dict(version="production-phase6-v1", state="running", run_id="fixture-1", users=5, elapsed_s=1,
        category="mixed", counts={"accepted":2}, series=[{"elapsed_s":1,"users":5}],
        questions="PRIVATE QUESTION", token="PRIVATE TOKEN")
    path = tmp_path/"status.json"
    path.write_text(json.dumps(raw))
    result = benchmark_status(tmp_path)
    assert result["counts"]["accepted"] == 2 and "PRIVATE" not in json.dumps(result)
    raw["users"] = float("nan")
    path.write_text(json.dumps(raw))
    assert benchmark_status(tmp_path) is None
    path.write_bytes(b" "*(1024**2+1))
    assert benchmark_status(tmp_path) is None


def test_live_history_rates_use_actual_intervals_and_stay_bounded(monkeypatch):
    now = [0.]
    monkeypatch.setattr("blackgrid.operations.dashboard.time.monotonic", lambda:now[0])
    view = LiveView()
    snapshot = dict(resources={"cpu_usage_seconds":2,"memory_current_bytes":100}, jobs={"queued":2,"running":1,"completed":0},
        api={"p50_seconds":.1,"p95_seconds":.2,"p99_seconds":.3},charged_usd=0,reserved_or_held_usd=0)
    view.project(snapshot,10)
    now[0] = 5
    snapshot["resources"]["cpu_usage_seconds"] = 3
    row = view.project(snapshot,20)[-1]
    assert row["requests_per_second"] == 2 and row["cpu_percent_of_one_core"] == 20
    for i in range(800):
        now[0] += 5
        view.project(snapshot,20+i)
    assert len(view.points) == 720
