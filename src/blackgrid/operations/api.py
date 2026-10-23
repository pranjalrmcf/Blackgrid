"""Opt-in authenticated API. The trusted local console is never mounted here."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, HTMLResponse, PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import Field, model_validator
from starlette.exceptions import HTTPException

from blackgrid.contracts import Contract, RunConfig
from blackgrid.operations.api_jobs import APIError, Jobs, Submission
from blackgrid.operations.health import readiness
from blackgrid.operations.settings import Settings
from blackgrid.operations import telemetry
from blackgrid.operations.monitoring import Monitoring, dashboard
from blackgrid.operations.dashboard import Sessions, LiveView, ASSETS, COOKIE, PATH as DASHBOARD_PATH, benchmark_status

SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
JOB_ID = re.compile(r"[a-f0-9]{32}\Z")


class Client(Contract):
    subject: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    token_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    operator: bool = Field(default=False, strict=True)


class Credentials(Contract):
    clients: tuple[Client, ...] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def unique(self):
        if len({x.token_sha256 for x in self.clients}) != len(self.clients):
            raise ValueError("duplicate credentials")
        return self


def load_credentials(path: Path) -> Credentials:
    if path.is_symlink() or path.stat().st_size > 256_000:
        raise ValueError("invalid credential file")
    return Credentials.model_validate_json(path.read_bytes())


class Rates:
    """Fixed-memory sliding refill buckets; only configured subjects become keys."""
    def __init__(self, limit=60, clock=time.monotonic):
        self.limit, self.clock = limit, clock
        self.entries: dict[str, tuple[float, float]] = {}
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        with self.lock:
            now = self.clock()
            tokens, last = self.entries.get(key, (float(self.limit), now))
            tokens = min(self.limit, tokens + max(0, now - last) * self.limit / 60)
            allowed = tokens >= 1
            self.entries[key] = (tokens - int(allowed), now)
            return allowed


class Listener(Contract):
    host: Literal["127.0.0.1", "0.0.0.0"] = "127.0.0.1"
    credentials_file: Path
    certfile: Path | None = None
    keyfile: Path | None = None
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost")

    @model_validator(mode="after")
    def transport(self):
        if bool(self.certfile) != bool(self.keyfile) or (self.host != "127.0.0.1" and not self.certfile):
            raise ValueError("TLS required for non-loopback API")
        if not self.allowed_hosts or any(not re.fullmatch(r"[a-zA-Z0-9.-]{1,253}", h) for h in self.allowed_hosts):
            raise ValueError("invalid allowed hosts")
        return self


def launch(settings: Settings) -> int:
    import uvicorn
    names = {"host": "HOST", "credentials_file": "CREDENTIALS_FILE", "certfile": "TLS_CERTFILE",
             "keyfile": "TLS_KEYFILE"}
    values = {field: os.environ["BLACKGRID_API_" + suffix] for field, suffix in names.items()
              if "BLACKGRID_API_" + suffix in os.environ}
    if "BLACKGRID_API_ALLOWED_HOSTS" in os.environ:
        values["allowed_hosts"] = tuple(os.environ["BLACKGRID_API_ALLOWED_HOSTS"].split(","))
    listener = Listener.model_validate(values)
    credentials = load_credentials(listener.credentials_file)
    app = create_app(settings, credentials, allowed_hosts=listener.allowed_hosts)
    uvicorn.run(app, host=listener.host, port=settings.port, workers=1, access_log=False,
                log_level="warning", server_header=False, proxy_headers=False, ws="none", http="h11",
                limit_concurrency=32, backlog=32, timeout_keep_alive=5, h11_max_incomplete_event_size=16384,
                timeout_graceful_shutdown=int(settings.shutdown_grace_seconds),
                ssl_certfile=str(listener.certfile) if listener.certfile else None,
                ssl_keyfile=str(listener.keyfile) if listener.keyfile else None)
    return 0


def create_app(settings: Settings, credentials: Credentials, *, allowed_hosts=("127.0.0.1", "localhost")) -> FastAPI:
    service: Jobs | None = None
    rates, admission = Rates(), Rates(300)
    bearer = HTTPBearer(auto_error=False)
    monitoring = Monitoring()
    sessions, live_view = Sessions(), LiveView()

    @asynccontextmanager
    async def lifespan(app):
        nonlocal service
        settings.runs_dir.mkdir(parents=True, exist_ok=True)
        settings.cache_dir.mkdir(parents=True, exist_ok=True)
        config = RunConfig.model_validate_json(settings.config.read_bytes())
        if (config.scope != "first_window" or config.investigation_family != "community"
                or not config.limits.within_first_window_limits() or config.deadline_s > 900):
            raise ValueError("API requires a bounded first-window base configuration")
        if readiness(settings, probe_server=False):
            raise ValueError("API deployment not ready")
        if settings.benchmark_mock_profile != "none" and (settings.environment != "test"
                or not config.dataset.source_url.startswith("blackgrid-synthetic-v1:")
                or os.environ.get("BLACKGRID_API_LIVE_POLICY_FILE")):
            raise ValueError("benchmark mock requires isolated synthetic test service without live policy")
        service = Jobs(settings)
        app.state.jobs = service
        try:
            yield
        finally:
            await asyncio.to_thread(service.close)

    app = FastAPI(title="BLACKGRID API", version="1.0", docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)
    app.state.monitoring = monitoring
    app.state.dashboard_sessions = sessions

    def failure(status: int, code: str, request: Request):
        request.state.error_category = code
        headers = {"WWW-Authenticate": "Bearer"} if status == 401 else {}
        if status in (429, 503):
            headers["Retry-After"] = "1"
        return JSONResponse({"error": {"code": code, "request_id": request.state.request_id}},
                            status_code=status, headers=headers)

    @app.exception_handler(APIError)
    async def api_error(request, exc):
        return failure(exc.status, exc.code, request)

    @app.exception_handler(sqlite3.Error)
    async def storage_error(request, exc):
        service.scheduler_failed = True
        return failure(503, "job_storage_unavailable", request)

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        return failure(422, "invalid_request", request)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return failure(exc.status_code, "not_found" if exc.status_code == 404 else "method_not_allowed", request)

    async def boundary(request: Request, call_next):
        try:
            headers = request.headers
            host = headers.get("host", "")
            permitted = {h for h in allowed_hosts} | {f"{h}:{settings.port}" for h in allowed_hosts}
            if host not in permitted or len(headers.getlist("host")) != 1:
                raise APIError(400, "invalid_host")
            if not admission.allow("global"):
                raise APIError(429, "rate_limited")
            dashboard_route = request.url.path == DASHBOARD_PATH or request.url.path.startswith(DASHBOARD_PATH + "/")
            expected_origin = f"https://{host}"
            if headers.get("origin") is not None and not (dashboard_route and request.url.scheme == "https"
                    and headers.get("origin") == expected_origin and len(headers.getlist("origin")) == 1):
                raise APIError(403, "cross_origin_forbidden")
            if dashboard_route and request.method == "POST" and (request.url.scheme != "https"
                    or headers.get("origin") != expected_origin or len(headers.getlist("origin")) != 1):
                raise APIError(403, "same_origin_required")
            if request.method not in ("GET", "POST"):
                raise APIError(405, "method_not_allowed")
            if request.url.query or len(request.url.path) > 256:
                raise APIError(400, "invalid_request")
            if request.method == "POST":
                if headers.get("transfer-encoding") or len(headers.getlist("content-length")) != 1:
                    raise APIError(411, "content_length_required")
                length = headers.get("content-length", "")
                if len(length) > 10 or not length.isascii() or not length.isdecimal() or int(length) > 4096:
                    raise APIError(413, "request_too_large")
                if headers.get("content-type", "").split(";")[0].lower() != "application/json":
                    raise APIError(415, "json_required")
                # Bounded streaming before framework JSON parsing, including dishonest lengths.
                chunks, total = [], 0
                async def collect():
                    nonlocal total
                    async for chunk in request.stream():
                        total += len(chunk)
                        if total > 4096:
                            raise APIError(413, "request_too_large")
                        chunks.append(chunk)
                await asyncio.wait_for(collect(), timeout=5)
                if total != int(length):
                    raise APIError(400, "invalid_request")
                request._body = b"".join(chunks)
                def unique_keys(pairs):
                    obj = {}
                    for key, value in pairs:
                        if key in obj:
                            raise ValueError("duplicate key")
                        obj[key] = value
                    return obj
                try:
                    json.loads(request._body, object_pairs_hook=unique_keys)
                except (ValueError, UnicodeError, RecursionError):
                    raise APIError(422, "invalid_request") from None
            response = await call_next(request)
        except APIError as exc:
            response = failure(exc.status, exc.code, request)
        except TimeoutError:
            response = failure(408, "request_timeout", request)
        except Exception:
            response = failure(500, "internal_error", request)
        response.headers.update({"X-Request-ID": request.state.request_id,
            "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer", "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'"})
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        if request.url.path == DASHBOARD_PATH or request.url.path.startswith(DASHBOARD_PATH + "/assets/"):
            response.headers["Content-Security-Policy"] = ("default-src 'none'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
        return response

    @app.middleware("http")
    async def observe_request(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex
        context = dict(trace_id=request.state.request_id, request_id=request.state.request_id,
                       job_id=None, tenant_id=None)
        started = time.perf_counter()
        monitoring.begin()
        status = 500
        try:
            with telemetry.span("api_request", context=context):
                response = await boundary(request, call_next)
                status = response.status_code
                job_context = None
                if getattr(request.state, "job_id", None) and getattr(request.state, "owner", None):
                    job_context = telemetry.job_context(service.folder(request.state.owner, request.state.job_id),
                                                        request.state.owner, request.state.job_id)
                with telemetry.span("final_response", context=job_context):
                    response.headers["X-Trace-ID"] = request.state.request_id
                return response
        finally:
            duration = time.perf_counter() - started
            route = request.scope.get("route")
            # Framework templates only: user paths, question text and IDs are never metric labels.
            route_name = route.path if route else "unmatched"
            monitoring.finish(route_name, status, duration)
            telemetry.emit(dict(timestamp=telemetry.datetime.now(telemetry.UTC).isoformat(),
                component="api", severity="ERROR" if status >= 500 else "INFO", event="request_completed",
                request_id=request.state.request_id, trace_id=request.state.request_id,
                job_id=getattr(request.state, "job_id", None),
                tenant_id=getattr(request.state, "tenant_id", None), route=route_name,
                status=status, error_category=getattr(request.state, "error_category", None), duration_s=round(duration, 6)))

    def identity(request: Request, token: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
        if (len(request.headers.getlist("authorization")) != 1 or token is None
                or not 32 <= len(token.credentials) <= 256 or not token.credentials.isascii()):
            raise APIError(401, "unauthorized")
        digest = hashlib.sha256(token.credentials.encode()).hexdigest()
        owner = None
        for client in credentials.clients:
            if secrets.compare_digest(digest, client.token_sha256):
                owner = client.subject
        if owner is None:
            raise APIError(401, "unauthorized")
        request.state.tenant_id = hashlib.sha256(owner.encode()).hexdigest()
        request.state.owner = owner
        if not rates.allow(owner):
            raise APIError(429, "rate_limited")
        return owner

    def operator(owner: str = Depends(identity)):
        if not any(c.subject == owner and c.operator for c in credentials.clients):
            raise APIError(403, "operator_required")
        return owner

    def browser_operator(request: Request):
        owner = sessions.owner(request.cookies.get(COOKIE))
        if owner is None:
            raise APIError(401, "dashboard_session_required")
        if not any(c.subject == owner and c.operator for c in credentials.clients):
            raise APIError(403, "operator_required")
        if not rates.allow(owner):
            raise APIError(429, "rate_limited")
        request.state.owner = owner
        request.state.tenant_id = hashlib.sha256(owner.encode()).hexdigest()
        return owner

    def owned(owner, job_id, request=None):
        if not JOB_ID.fullmatch(job_id):
            raise APIError(404, "not_found")
        row = service.row(owner, job_id)
        if request is not None:
            request.state.job_id = job_id
        return row

    @app.get("/health/live")
    def live():
        return {"status": "live"}

    @app.get("/health/ready")
    def ready():
        failures = readiness(settings, probe_server=False)
        if service and not service.available():
            failures.append("job_scheduler_unavailable")
        return JSONResponse({"status": "unavailable" if failures else "ready", "failures": failures},
                            status_code=503 if failures else 200)

    @app.post("/api/v1/jobs")
    def submit(body: Submission, response: Response, request: Request, owner: str = Depends(identity),
               idempotency_key: str | None = Header(default=None)):
        if not idempotency_key or not SAFE_ID.fullmatch(idempotency_key):
            raise APIError(400, "invalid_idempotency_key")
        job, created = service.submit(owner, idempotency_key, body)
        request.state.job_id = job["job_id"]
        response.status_code = 202 if created else 200
        response.headers["Location"] = f"/api/v1/jobs/{job['job_id']}"
        return job

    @app.get("/api/v1/jobs/{job_id}/trace")
    def job_trace(job_id: str, request: Request, owner: str = Depends(identity)):
        owned(owner, job_id, request)
        path = service.folder(owner, job_id) / "telemetry.jsonl"
        spans = telemetry.read_spans(path)
        starts = {s["span_id"] for s in spans if s["event"] == "start"}
        ends = {s["span_id"] for s in spans if s["event"] == "end"}
        return {"trace_id": job_id, "spans": spans, "open_span_ids": sorted(starts - ends),
                "available": bool(spans), "byte_limit": telemetry.LIMIT,
                "limit_reached": path.is_file() and not path.is_symlink() and path.stat().st_size >= telemetry.LIMIT - 2048}

    @app.get("/api/v1/metrics")
    def metrics(owner: str = Depends(operator)):
        return PlainTextResponse(monitoring.prometheus(monitoring.snapshot(service)),
                                 media_type="text/plain; version=0.0.4")

    @app.get("/api/v1/monitoring.json")
    def monitor_json(owner: str = Depends(operator)):
        return monitoring.snapshot(service)

    @app.get("/api/v1/monitoring")
    def monitor_page(owner: str = Depends(operator)):
        return HTMLResponse(dashboard(monitoring.snapshot(service)))

    @app.get(DASHBOARD_PATH)
    def live_dashboard():
        return HTMLResponse((ASSETS / "index.html").read_text(encoding="utf-8"))

    @app.get(DASHBOARD_PATH + "/assets/{name}")
    def dashboard_asset(name: str):
        types = {"app.js": "text/javascript", "style.css": "text/css"}
        if name not in types:
            raise APIError(404, "not_found")
        return Response((ASSETS / name).read_bytes(), media_type=types[name])

    @app.post(DASHBOARD_PATH + "/session")
    def browser_session(body: dict, response: Response, owner: str = Depends(operator)):
        if body:
            raise APIError(422, "invalid_request")
        token = sessions.issue(owner)
        if token is None:
            raise APIError(503, "dashboard_session_limit")
        response.set_cookie(COOKIE, token, max_age=sessions.ttl, secure=True, httponly=True,
                            samesite="strict", path=DASHBOARD_PATH)
        return {"status": "signed_in", "expires_in_seconds": sessions.ttl}

    @app.post(DASHBOARD_PATH + "/logout")
    def browser_logout(body: dict, request: Request, response: Response, owner: str = Depends(browser_operator)):
        if body:
            raise APIError(422, "invalid_request")
        sessions.revoke(request.cookies.get(COOKIE))
        response.delete_cookie(COOKIE, path=DASHBOARD_PATH, secure=True, httponly=True, samesite="strict")
        return {"status": "signed_out"}

    @app.get(DASHBOARD_PATH + "/data")
    def browser_data(owner: str = Depends(browser_operator)):
        snapshot = monitoring.snapshot(service)
        with monitoring.lock:
            total = sum(monitoring.requests.values())
        return {"snapshot": snapshot, "history": live_view.project(snapshot, total),
                "benchmark": benchmark_status(settings.benchmark_results_dir), "refresh_seconds": 5}

    @app.get("/api/v1/benchmark/identity")
    def benchmark_identity(owner: str = Depends(operator)):
        if settings.environment != "test" or settings.benchmark_mock_profile != "latency" or service.live_policy:
            raise APIError(404, "not_found")
        config = RunConfig.model_validate_json(settings.config.read_bytes())
        if not config.dataset.source_url.startswith("blackgrid-synthetic-v1:"):
            raise APIError(404, "not_found")
        return {"version": "production-phase6-v1", "origin": "synthetic", "mode": "mock",
                "live_enabled": False, "mock_profile": "latency", "worker_slots": 1,
                "queue_slots": service.QUEUE_CAPACITY, "data_sha256": config.dataset.sha256,
                "config_sha256": service.config_sha256}

    @app.get("/api/v1/jobs/{job_id}")
    def status(job_id: str, request: Request, owner: str = Depends(identity)):
        return service.public(owned(owner, job_id, request))

    @app.get("/api/v1/capabilities")
    def capabilities(owner: str = Depends(identity)):
        from blackgrid.operations.api_tools import CATALOG
        from blackgrid.workflow.evidence import ToolEvidence
        binding = ToolEvidence.capture(settings.evidence_root)
        return {"routing": "auto", "tools": [{"name": name, "family": family, "analysis": description,
            "available": binding.forecast_ready() if family == "forecast" else "research" in binding.files
                if family == "research" else True} for name, (family, description) in CATALOG.items()]}

    @app.post("/api/v1/jobs/{job_id}/cancel")
    def cancel(job_id: str, body: dict, request: Request, owner: str = Depends(identity)):
        owned(owner, job_id, request)
        if body:
            raise APIError(422, "invalid_request")
        return service.request_cancel(owner, job_id)

    @app.get("/api/v1/jobs/{job_id}/results")
    def results(job_id: str, request: Request, owner: str = Depends(identity)):
        owned(owner, job_id, request)
        return service.results(owner, job_id)

    @app.get("/api/v1/jobs/{job_id}/artifacts/{artifact}")
    def artifact(job_id: str, artifact: str, request: Request, owner: str = Depends(identity)):
        owned(owner, job_id, request)
        if artifact != "summary.json":
            raise APIError(404, "not_found")
        return JSONResponse(service.results(owner, job_id),
                            headers={"Content-Disposition": 'attachment; filename="summary.json"'})

    @app.get("/api/v1/openapi.json")
    def schema(owner: str = Depends(identity)):
        return app.openapi()

    return app
