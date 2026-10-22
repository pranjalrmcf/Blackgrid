"""Local, live investigation console (standard library only).

Safety rules:
* binds to 127.0.0.1 only, and rejects requests whose Host header is not this console
  (blocks DNS-rebinding pages from reaching the API);
* every state-changing request needs the per-session token embedded in the served page;
* actions are a fixed allowlist that run the same CLI code paths and gates as the terminal;
  default mock only; CLI-authorized live mode consumes a retained USD 0.50 allowance;
  browser requests cannot create or renew that allowance;
* one background job at a time; run IDs are validated against the runs directory;
* strict response headers (no framing, no sniffing, same-origin connections only).
"""

from __future__ import annotations

import json
import secrets
import threading
import traceback
import uuid
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from blackgrid.console.data import forecast_payload, index_payload, is_run, pilot_payload, resolve, run_payload
from blackgrid.console.render import live_page

MAX_BODY = 4_096
EXIT_MESSAGES = {0: "completed", 1: "refused or invalid", 2: "finished without completing (see the run)",
                 3: "paused (see the run)"}
HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Content-Security-Policy": ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                                "connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'; "
                                "frame-ancestors 'none'"),
}


class Console:
    def __init__(self, runs_dir: Path, cache_dir: Path, config: Path, data_root: Path, port: int,
                 full_config: Path | None = None, live_allowance: Path | None = None) -> None:
        self.runs_dir, self.cache_dir, self.config, self.data_root = runs_dir, cache_dir, config, data_root
        self.full_config = full_config or config.parent / "collegemsg_full.json"
        self.port = port
        self.live_allowance = live_allowance
        self.token = secrets.token_urlsafe(32)
        self.jobs: dict[str, dict] = {}
        self.lock = threading.Lock()
        self.busy: str | None = None
        self.stopping = False
        self._workers: set[threading.Thread] = set()

    def stop_admission(self) -> None:
        with self.lock:
            self.stopping = True

    def drain(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        with self.lock:
            workers = list(self._workers)
        for worker in workers:
            worker.join(max(0, deadline - time.monotonic()))
        return all(not worker.is_alive() for worker in workers)

    # --- actions (all through the CLI's own code paths and gates) ---------------------------------

    def argv(self, body: dict) -> list[str]:
        action = body.get("action")
        common = ["--runs-dir", str(self.runs_dir), "--cache-dir", str(self.cache_dir)]
        if action == "start":
            mode = body.get("mode", "mock")
            if mode not in ("mock", "live") or (mode == "live" and self.live_allowance is None):
                raise ValueError("real AI requires console startup with --allow-paid")
            condition = body.get("condition", "validated")
            if condition not in ("validated", "tool_only"):
                raise ValueError("condition must be validated or tool_only")
            scope = body.get("scope", "first_window")
            if scope not in ("first_window", "full_dataset"):
                raise ValueError("scope must be first_window or full_dataset")
            config = self.full_config if scope == "full_dataset" else self.config
            if mode == "live":
                from blackgrid.agent.live_allowance import read_allowance
                remaining = read_allowance(self.live_allowance, self.runs_dir)["remaining_usd"]
                if remaining <= .000001:
                    raise ValueError("live allowance exhausted")
                config = self.config.parent / ("collegemsg_full_live.json" if scope == "full_dataset" else "collegemsg_live.json")
            argv = ["run", str(config), "--mode", mode, "--condition", condition,
                    "--data-root", str(self.data_root), *common]
            if mode == "live":
                argv += ["--allow-paid", "--live-allowance", str(self.live_allowance)]
                if body.get("adaptive", False) not in (True, False):
                    raise ValueError("adaptive must be a boolean")
                argv += ["--planning-mode", "adaptive" if body.get("adaptive", False) else "single"]
            if "question" in body:
                question = body["question"]
                if not isinstance(question, str) or not 1 <= len(question.strip()) <= 500:
                    raise ValueError("question must contain 1 to 500 characters")
                argv += ["--family", "auto", "--question", question.strip()]
            return argv
        if action == "pilot":
            return ["pilot", *common]
        if action in ("resume", "cancel", "deny", "reconcile"):
            run_id = str(body.get("run_id", ""))
            path = resolve(self.runs_dir, run_id)
            if path is None or "/" in run_id or not is_run(path):
                raise ValueError("unknown run")
            argv = [action, run_id, *common]
            if action == "reconcile":
                choice = body.get("choice")
                if choice not in ("retry", "stop"):
                    raise ValueError("choice must be retry or stop")
                argv.append(f"--{choice}")
            return argv  # never --allow-paid: paid authorization stays on the command line
        raise ValueError("action not allowed")

    def start_job(self, body: dict) -> dict:
        argv = self.argv(body)
        # Cancellation is exempt from the one-job limit: it is most useful while another job runs. It is
        # safe alongside it because the run lock decides who may touch a run; for the run that is
        # working right now, cancel only raises its flag and the worker stops at its next boundary.
        exclusive = body.get("action") != "cancel"
        with self.lock:
            if self.stopping:
                raise RuntimeError("console is shutting down")
            if exclusive and self.busy is not None:
                raise RuntimeError("another action is still running (cancel is always allowed)")
            job_id = uuid.uuid4().hex[:12]
            if exclusive:
                self.busy = job_id
            self.jobs[job_id] = {"job_id": job_id, "action": body.get("action"), "state": "running",
                                 "started_utc": datetime.now(UTC).isoformat()}

        def work() -> None:
            from blackgrid.cli import main

            job = self.jobs[job_id]
            try:
                code = main(argv)
                job.update(state="done" if code in (0, 2, 3) else "error", exit_code=code,
                           message=EXIT_MESSAGES.get(code, f"exit {code}"))
            except BaseException as exc:  # never kill the server; keep the reason visible
                job.update(state="error", message=f"{type(exc).__name__}: {exc}"[:300])
                traceback.print_exc()
            finally:
                job["finished_utc"] = datetime.now(UTC).isoformat()
                with self.lock:
                    if exclusive:
                        self.busy = None
                    self._workers.discard(threading.current_thread())

        worker = threading.Thread(target=work, name=f"console-job-{job_id}", daemon=True)
        with self.lock:
            # Shutdown may have begun since validation; do not launch new work.
            if self.stopping:
                self.jobs[job_id].update(state="error", message="console is shutting down")
                if exclusive:
                    self.busy = None
                raise RuntimeError("console is shutting down")
            self._workers.add(worker)
            worker.start()
        return self.jobs[job_id]

    def live_run(self, run_id: str) -> dict:
        path = resolve(self.runs_dir, run_id)
        if path is None or not is_run(path):
            raise LookupError("unknown run")
        payload = run_payload(self.runs_dir, path)
        payload["locked"] = False
        db = path.parent / "workflow.sqlite"
        if db.is_file():
            from blackgrid.workflow.store import OperationStore, StoreError

            store = OperationStore(db)
            try:
                row = store.run(path.name)
                payload["locked"] = bool(row["lock_owner"])
                payload["summary"]["status"] = row["status"]
            except StoreError:
                pass
            finally:
                store.close()
        return payload


def make_handler(console: Console):
    allowed_hosts = {f"127.0.0.1:{console.port}", f"localhost:{console.port}"}

    class Handler(BaseHTTPRequestHandler):
        server_version = "BlackgridConsole"
        sys_version = ""

        def log_message(self, fmt: str, *args) -> None:  # quiet: no request bodies or tokens in logs
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in HEADERS.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, payload: object) -> None:
            self._send(code, json.dumps(payload, default=str).encode("utf-8"), "application/json; charset=utf-8")

        def _host_ok(self) -> bool:
            if self.headers.get("Host") not in allowed_hosts:
                self._json(403, {"error": "forbidden host"})
                return False
            return True

        def do_GET(self) -> None:  # noqa: N802
            if not self._host_ok():
                return
            url = urlparse(self.path)
            query = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                if url.path == "/health/live":
                    self._json(503 if console.stopping else 200,
                               {"status": "stopping" if console.stopping else "live"})
                elif url.path == "/":
                    self._send(200, live_page(console.token).encode("utf-8"), "text/html; charset=utf-8")
                elif url.path == "/api/index":
                    data = index_payload(console.runs_dir)
                    data["live"] = {"enabled": False}
                    if console.live_allowance:
                        from blackgrid.agent.live_allowance import read_allowance
                        try:
                            allowance = read_allowance(console.live_allowance, console.runs_dir)
                            data["live"] = {key: allowance[key] for key in ("model", "cap_usd", "spent_usd", "remaining_usd")}
                            data["live"]["enabled"] = allowance["remaining_usd"] > .000001
                        except (OSError, ValueError):
                            data["live"] = {"enabled": False, "error": "Live allowance unavailable"}
                    self._json(200, data)
                elif url.path == "/api/run":
                    self._json(200, console.live_run(query.get("id", "")))
                elif url.path == "/api/pilot":
                    path = resolve(console.runs_dir, query.get("id", ""))
                    if path is None or not (path / "pilot.json").is_file():
                        raise LookupError("unknown pilot")
                    self._json(200, pilot_payload(console.runs_dir, path))
                elif url.path == "/api/forecast":
                    path = resolve(console.runs_dir, query.get("id", ""))
                    if path is None or not (path / "forecast.json").is_file():
                        raise LookupError("unknown forecast")
                    self._json(200, forecast_payload(console.runs_dir, path))
                elif url.path == "/api/job":
                    job = console.jobs.get(query.get("id", ""))
                    self._json(200, job) if job else self._json(404, {"error": "unknown job"})
                else:
                    self._json(404, {"error": "not found"})
            except LookupError as exc:
                self._json(404, {"error": str(exc)})

        def do_POST(self) -> None:  # noqa: N802
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            if length < 0 or length > MAX_BODY:
                self.close_connection = True
                return self._json(413, {"error": "request too large or malformed"})
            raw = self.rfile.read(length)  # always consume the body before replying (Windows aborts otherwise)
            if not self._host_ok():
                return
            if urlparse(self.path).path != "/api/action":
                return self._json(404, {"error": "not found"})
            if not secrets.compare_digest(self.headers.get("X-Blackgrid-Token", ""), console.token):
                return self._json(403, {"error": "missing or wrong token"})
            if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                return self._json(415, {"error": "JSON only"})
            try:
                body = json.loads(raw or b"{}")
                if not isinstance(body, dict):
                    raise ValueError("expected an object")
                self._json(202, console.start_job(body))
            except RuntimeError as exc:
                self._json(409, {"error": str(exc)})
            except (ValueError, json.JSONDecodeError) as exc:
                self._json(400, {"error": str(exc)})

    return Handler


def serve(console: Console) -> ThreadingHTTPServer:
    """Create (not start) the server; bound to loopback only."""
    server = ThreadingHTTPServer(("127.0.0.1", console.port), make_handler(console))
    # Client connections must not extend shutdown beyond the action drain budget.
    server.daemon_threads = True
    return server
