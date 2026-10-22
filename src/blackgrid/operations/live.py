"""Operator-authorized live API policy and private OpenRouter transport broker."""
from __future__ import annotations

import hashlib
import json
import math
import os
import select
import socket
import struct
import subprocess
import sys
import threading
from pathlib import Path

from pydantic import Field

from blackgrid.contracts import Contract, RunConfig

LIMIT = 9 * 1024 * 1024


class LivePolicy(Contract):
    version: str = "api-live-v1"
    model: str = Field(min_length=1, max_length=200)
    prior_spend_usd: float = Field(ge=0, allow_inf_nan=False)
    ceiling_project_usd: float = Field(gt=0, le=10, allow_inf_nan=False)
    max_per_job_usd: float = Field(default=.15, gt=0, le=.15, allow_inf_nan=False)
    subjects: tuple[str, ...] = Field(min_length=1, max_length=1000)
    config: Path
    key_file: Path

    def config_for(self, baseline: RunConfig, other_spend: float) -> RunConfig:
        live = RunConfig.model_validate_json(self.config.read_bytes())
        for field in ("dataset", "window", "projection", "limits", "experiment", "scope"):
            if getattr(live, field) != getattr(baseline, field):
                raise ValueError("live config changes the approved scientific specification")
        raw = live.model_dump(mode="json")
        raw.update(mode="live", paid_execution_authorized=True)
        raw["llm"]["model"] = self.model
        raw["budget"].update(max_usd_total=self.ceiling_project_usd,
            max_usd_current_sprint=self.ceiling_project_usd,
            max_usd_per_investigation=min(self.max_per_job_usd, self.ceiling_project_usd - other_spend))
        return RunConfig.model_validate(raw)

    def key(self) -> str:
        if self.key_file.is_symlink() or self.key_file.stat().st_size > 4096:
            raise ValueError("invalid provider secret file")
        value = self.key_file.read_text().strip()
        if not value or not value.isascii() or any(c.isspace() for c in value):
            raise ValueError("invalid provider secret")
        return value


def load_policy() -> LivePolicy | None:
    path = os.environ.get("BLACKGRID_API_LIVE_POLICY_FILE")
    if not path:
        return None
    source = Path(path)
    if source.is_symlink() or source.stat().st_size > 256_000:
        raise ValueError("invalid live policy")
    return LivePolicy.model_validate_json(source.read_bytes())


def receive(connection: socket.socket) -> dict:
    def exact(size):
        result = bytearray()
        while len(result) < size:
            chunk = connection.recv(size - len(result))
            if not chunk:
                raise EOFError
            result.extend(chunk)
        return bytes(result)
    size = struct.unpack("!I", exact(4))[0]
    if size > LIMIT:
        raise ValueError("broker message too large")
    result = json.loads(exact(size))
    if not isinstance(result, dict):
        raise ValueError("invalid broker message")
    return result


def send(connection: socket.socket, payload: dict):
    raw = json.dumps(payload).encode()
    if len(raw) > LIMIT:
        raise ValueError("broker message too large")
    connection.sendall(struct.pack("!I", len(raw)) + raw)


def broker_request(payload: dict, policy: LivePolicy) -> dict:
    from blackgrid.agent.http_transport import ENDPOINTS
    url, method = payload.get("url"), payload.get("method")
    timeout = payload.get("timeout_s")
    if (not isinstance(url, str) or ENDPOINTS.get(url) != method or isinstance(timeout, bool)
            or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 60):
        return {"ok": False, "category": "permanent", "error": "Provider request not permitted"}
    body = payload.get("body")
    if method == "POST" and (not isinstance(body, dict) or body.get("model") != policy.model):
        return {"ok": False, "category": "permanent", "error": "Provider model not permitted"}
    # Replace all client headers. The actual key exists only in the broker/HTTP child.
    payload = {"url": url, "method": method, "body": body, "timeout_s": timeout,
               "deny_redirects": True,
               "headers": {"Authorization": "Bearer " + policy.key(), "Content-Type": "application/json",
                           "X-Title": "BLACKGRID"}}
    try:
        result = subprocess.run([sys.executable, "-m", "blackgrid.agent.http_transport"],
            input=json.dumps(payload).encode(), capture_output=True, timeout=timeout + 1, check=False)
        reply = json.loads(result.stdout) if len(result.stdout) <= LIMIT else None
        if result.returncode or not isinstance(reply, dict):
            raise ValueError
        return reply
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return {"ok": False, "category": "uncertain", "error": "Provider transport unavailable"}


class Broker:
    def __init__(self, policy: LivePolicy):
        if sys.platform != "linux":
            raise ValueError("live API workers require the Linux container")
        self.policy = policy
        self.failure_code = None
        self.parent, self.child = socket.socketpair()
        self.parent.settimeout(65)
        self.thread = threading.Thread(target=self.serve, daemon=True)

    def serve(self):
        try:
            while True:
                if not select.select([self.parent], [], [], 1)[0]:
                    continue
                payload = receive(self.parent)
                reply = broker_request(payload, self.policy)
                if not reply.get("ok"):
                    self.failure_code = ("pricing_unavailable" if payload.get("method") == "GET" else
                        "provider_billing_uncertain" if reply.get("category") == "uncertain" else "provider_request_failed")
                elif payload.get("method") == "GET":
                    models = reply.get("response", {}).get("data", [])
                    if not any(isinstance(m, dict) and m.get("id") == self.policy.model for m in models):
                        self.failure_code = "pricing_unavailable"
                send(self.parent, reply)
        except (OSError, ValueError, EOFError):
            pass
        finally:
            self.parent.close()

    def start(self):
        self.child.close()
        self.thread.start()

    def close(self):
        self.child.close()
        try:
            self.parent.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.parent.close()
        if self.thread.is_alive():
            self.thread.join(2)


def worker_request(payload: dict) -> dict:
    # FD is a private inherited socketpair, not an address or client-selected endpoint.
    fd = int(os.environ["BLACKGRID_PROVIDER_BROKER_FD"])
    connection = socket.socket(fileno=fd)
    connection.settimeout(min(60, float(payload.get("timeout_s", 60))))
    try:
        send(connection, payload)
        return receive(connection)
    finally:
        connection.detach()
