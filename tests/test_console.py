"""The interactive console: snapshot safety, path validation, and the live server's guards."""

from __future__ import annotations

import http.client
import json
import socket
import threading
import time
from pathlib import Path

import pytest

from blackgrid.console.data import resolve
from blackgrid.console.render import embed
from blackgrid.console.server import Console, serve


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def console(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    con = Console(runs, tmp_path / "cache", Path("configs/collegemsg_sprint01.json"), tmp_path, free_port())
    httpd = serve(con)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield con
    httpd.shutdown()
    httpd.server_close()


def request(con: Console, method: str, path: str, body: object = None, *, token: str | None = None,
            host: str | None = None, ctype: str = "application/json") -> tuple[int, dict | str, dict]:
    conn = http.client.HTTPConnection("127.0.0.1", con.port, timeout=10)
    headers = {"Host": host or f"127.0.0.1:{con.port}"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers |= {"Content-Type": ctype, "Content-Length": str(len(data))}
    if token:
        headers["X-Blackgrid-Token"] = token
    conn.request(method, path, body=data, headers=headers)
    resp = conn.getresponse()
    raw = resp.read().decode()
    try:
        payload = json.loads(raw)
    except ValueError:
        payload = raw
    return resp.status, payload, dict(resp.getheaders())


def test_embedded_data_cannot_break_out_of_its_script_block():
    hostile = '</script><script>alert(1)</script><!-- & "quotes"'
    text = embed({"claim": hostile})
    assert "<" not in text and ">" not in text and "&" not in text.replace("\\u0026", "")
    assert json.loads(text)["claim"] == hostile


def test_run_ids_cannot_escape_the_runs_folder(tmp_path):
    (tmp_path / "runs" / "r1").mkdir(parents=True)
    (tmp_path / "secret").mkdir()
    runs = tmp_path / "runs"
    assert resolve(runs, "r1") == (runs / "r1").resolve()
    for bad in ("../secret", "..", "/etc", "r1/../../secret", "C:\\Windows", "r1/x/y", ""):
        assert resolve(runs, bad) is None, bad


def test_page_is_served_with_strict_headers_and_foreign_hosts_are_refused(console):
    status, page, headers = request(console, "GET", "/")
    assert status == 200 and console.token in page and '"mode": "live"' in page
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"] and headers["X-Frame-Options"] == "DENY"
    status, _, _ = request(console, "GET", "/api/index", host="evil.example:80")  # DNS-rebinding attempt
    assert status == 403


@pytest.mark.parametrize("body,token,ctype,code", [
    ({"action": "pilot"}, None, "application/json", 403),                      # no token
    ({"action": "pilot"}, "wrong", "application/json", 403),                   # wrong token
    ({"action": "pilot"}, "OK", "text/plain", 415),                           # not JSON
    ({"action": "shell", "cmd": "dir"}, "OK", "application/json", 400),       # not an allowed action
    ({"action": "cancel", "run_id": "../x"}, "OK", "application/json", 400),  # path traversal
    ({"action": "start", "condition": "live"}, "OK", "application/json", 400),  # no other modes
])
def test_actions_are_guarded(console, body, token, ctype, code):
    status, payload, _ = request(console, "POST", "/api/action", body,
                                 token=console.token if token == "OK" else token, ctype=ctype)
    assert status == code, payload


def test_cancel_is_accepted_while_another_job_is_running(console):
    """Regression (review 3, item 4): the one-job limit must not block cancellation."""
    from tests.test_workflow import Counting, dev_config, start

    run_id = start(console.runs_dir, Counting(live=True), None, config=dev_config("live")).outcome.run_id
    console.busy = "a-long-running-job"  # e.g. a mock run or the pilot is in progress
    status, payload, _ = request(console, "POST", "/api/action", {"action": "pilot"}, token=console.token)
    assert status == 409  # other actions still wait their turn
    status, job, _ = request(console, "POST", "/api/action", {"action": "cancel", "run_id": run_id},
                             token=console.token)
    assert status == 202
    for _ in range(100):
        _, job, _ = request(console, "GET", f"/api/job?id={job['job_id']}")
        if job["state"] != "running":
            break
        time.sleep(0.1)
    assert job["state"] == "done" and console.busy == "a-long-running-job"  # cancel never took the slot
    _, run, _ = request(console, "GET", f"/api/run?id={run_id}")
    assert run["summary"]["status"] == "cancelled"


def test_browser_can_deny_but_never_approve_paid_execution(console, tmp_path):
    from tests.test_workflow import Counting, dev_config, start

    out = start(console.runs_dir, Counting(live=True), None, config=dev_config("live"))
    run_id = out.outcome.run_id
    assert out.outcome.status == "paused"
    assert "--allow-paid" not in " ".join(console.argv({"action": "resume", "run_id": run_id}))
    status, run, _ = request(console, "GET", f"/api/run?id={run_id}")
    assert status == 200 and run["summary"]["status"] == "paused" and run["workflow"]["pause"]["kind"] == "authorization"
    assert "messages" not in json.dumps(run) and "llm_trace" not in run  # prompts never leave the run folder
    status, job, _ = request(console, "POST", "/api/action", {"action": "deny", "run_id": run_id}, token=console.token)
    assert status == 202
    for _ in range(100):
        _, job, _ = request(console, "GET", f"/api/job?id={job['job_id']}")
        if job["state"] != "running":
            break
        time.sleep(0.1)
    assert job["state"] == "done" and job["exit_code"] == 2
    _, run, _ = request(console, "GET", f"/api/run?id={run_id}")
    assert run["summary"]["status"] == "denied"
    _, index, _ = request(console, "GET", "/api/index")
    assert [r["status"] for r in index["runs"]] == ["denied"]
