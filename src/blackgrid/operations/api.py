"""Opt-in authenticated API. The trusted local console is never mounted here."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import secrets
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import Field, model_validator
from starlette.exceptions import HTTPException

from blackgrid.contracts import Contract, RunConfig
from blackgrid.operations.api_jobs import APIError, Jobs, Submission
from blackgrid.operations.health import readiness
from blackgrid.operations.settings import Settings

SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
JOB_ID = re.compile(r"[a-f0-9]{32}\Z")


class Client(Contract):
    subject: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    token_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


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

    @asynccontextmanager
    async def lifespan(app):
        nonlocal service
        settings.runs_dir.mkdir(parents=True, exist_ok=True)
        settings.cache_dir.mkdir(parents=True, exist_ok=True)
        config = RunConfig.model_validate_json(settings.config.read_bytes())
        if (config.scope != "first_window" or config.investigation_family != "community"
                or not config.limits.within_first_window_limits() or config.deadline_s > 900):
            raise ValueError("API requires bounded community configuration")
        if readiness(settings, probe_server=False):
            raise ValueError("API deployment not ready")
        service = Jobs(settings)
        app.state.jobs = service
        try:
            yield
        finally:
            await asyncio.to_thread(service.close)

    app = FastAPI(title="BLACKGRID API", version="1.0", docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)

    def failure(status: int, code: str, request: Request):
        headers = {"WWW-Authenticate": "Bearer"} if status == 401 else {}
        if status in (429, 503):
            headers["Retry-After"] = "1"
        return JSONResponse({"error": {"code": code, "request_id": request.state.request_id}},
                            status_code=status, headers=headers)

    @app.exception_handler(APIError)
    async def api_error(request, exc):
        return failure(exc.status, exc.code, request)

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        return failure(422, "invalid_request", request)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return failure(exc.status_code, "not_found" if exc.status_code == 404 else "method_not_allowed", request)

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex
        try:
            headers = request.headers
            host = headers.get("host", "")
            permitted = {h for h in allowed_hosts} | {f"{h}:{settings.port}" for h in allowed_hosts}
            if host not in permitted or len(headers.getlist("host")) != 1:
                raise APIError(400, "invalid_host")
            if not admission.allow("global"):
                raise APIError(429, "rate_limited")
            if headers.get("origin") is not None:
                raise APIError(403, "cross_origin_forbidden")
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
        return response

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
        if not rates.allow(owner):
            raise APIError(429, "rate_limited")
        return owner

    def owned(owner, job_id):
        if not JOB_ID.fullmatch(job_id):
            raise APIError(404, "not_found")
        return service.row(owner, job_id)

    @app.get("/health/live")
    def live():
        return {"status": "live"}

    @app.get("/health/ready")
    def ready():
        failures = readiness(settings, probe_server=False)
        return JSONResponse({"status": "unavailable" if failures else "ready", "failures": failures},
                            status_code=503 if failures else 200)

    @app.post("/api/v1/jobs")
    def submit(body: Submission, response: Response, owner: str = Depends(identity),
               idempotency_key: str | None = Header(default=None)):
        if not idempotency_key or not SAFE_ID.fullmatch(idempotency_key):
            raise APIError(400, "invalid_idempotency_key")
        job, created = service.submit(owner, idempotency_key, body)
        response.status_code = 202 if created else 200
        response.headers["Location"] = f"/api/v1/jobs/{job['job_id']}"
        return job

    @app.get("/api/v1/jobs/{job_id}")
    def status(job_id: str, owner: str = Depends(identity)):
        return service.public(owned(owner, job_id))

    @app.post("/api/v1/jobs/{job_id}/cancel")
    def cancel(job_id: str, body: dict, owner: str = Depends(identity)):
        owned(owner, job_id)
        if body:
            raise APIError(422, "invalid_request")
        return service.request_cancel(owner, job_id)

    @app.get("/api/v1/jobs/{job_id}/results")
    def results(job_id: str, owner: str = Depends(identity)):
        owned(owner, job_id)
        return service.results(owner, job_id)

    @app.get("/api/v1/jobs/{job_id}/artifacts/{artifact}")
    def artifact(job_id: str, artifact: str, owner: str = Depends(identity)):
        owned(owner, job_id)
        if artifact != "summary.json":
            raise APIError(404, "not_found")
        return JSONResponse(service.results(owner, job_id),
                            headers={"Content-Disposition": 'attachment; filename="summary.json"'})

    @app.get("/api/v1/openapi.json")
    def schema(owner: str = Depends(identity)):
        return app.openapi()

    return app
