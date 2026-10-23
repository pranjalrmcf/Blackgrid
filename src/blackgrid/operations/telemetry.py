"""Local, bounded, content-free spans. Never an execution or billing authority.

Cross-process context is passed only through the trusted worker environment. No
external exporter, incoming trace header, prompt, argument or exception text is used.
"""
from __future__ import annotations

import contextvars
import functools
import hashlib
import json
import math
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

CONTEXT = contextvars.ContextVar("blackgrid_trace", default=None)
LIMIT = 1024 * 1024
LOCK = threading.Lock()
WRITE_FAILURES = 0
NAMES = {"api_request", "job_scheduling", "agent_execution", "llm_call", "tool_call",
         "artifact_persistence", "final_response", "provider_request", "provider_rate_limit",
         "tool_selection_failure"}


def emit(event):
    """Only internally constructed records reach stdout; no arbitrary **attributes."""
    try:
        if event.get("tool"):
            from blackgrid.operations.api_tools import CATALOG
            if event["tool"] in CATALOG:
                event = event | {"analysis": CATALOG[event["tool"]][1]}
        print(json.dumps(event, separators=(",", ":"), allow_nan=False), flush=True)
    except (OSError, ValueError):
        pass


def read_spans(path: Path):
    if not path.is_file() or path.is_symlink():
        return []
    try:
        with path.open("rb") as source:
            data = source.read(LIMIT)
        records = []
        for line in data.splitlines():
            try:
                row = json.loads(line)
                # Files are not a route for arbitrary content into API responses/logs.
                if (set(row) != {"timestamp", "trace_id", "span_id", "parent_span_id", "request_id",
                        "job_id", "tenant_id", "component", "severity", "error_category", "duration_s",
                        "event", "name", "tool", "peak_rss_bytes"}
                    or row["name"] not in NAMES or row["event"] not in ("start", "end")
                    or row["component"] != "observability" or row["severity"] not in ("INFO", "ERROR")
                    or row["error_category"] not in (None, "execution_exception")
                    or not all(isinstance(row[k], str) and re.fullmatch(r"[a-f0-9]{32}", row[k])
                               for k in ("trace_id", "job_id"))
                    or not re.fullmatch(r"[a-f0-9]{16}", row["span_id"])
                    or any(row[k] is not None and not re.fullmatch(pattern, row[k])
                           for k, pattern in (("parent_span_id", r"[a-f0-9]{16}"),
                             ("request_id", r"[a-f0-9]{32}"), ("tenant_id", r"[a-f0-9]{64}")))
                    or not re.fullmatch(r"[0-9T:.+Z-]{10,40}", row["timestamp"])
                    or not isinstance(row["duration_s"], (int, float))
                    or not math.isfinite(row["duration_s"]) or not 0 <= row["duration_s"] <= 86400
                    or not isinstance(row["peak_rss_bytes"], int) or not 0 <= row["peak_rss_bytes"] <= 2**50):
                    continue
                from blackgrid.operations.api_tools import CATALOG
                if row["tool"] is not None and row["tool"] not in CATALOG:
                    continue
                records.append(row)
            except (ValueError, TypeError, KeyError):
                continue
        return records
    except OSError:
        return []


def _record_impl(context, name, span_id, parent, event, duration=0., failed=False, tool=None):
    global WRITE_FAILURES
    peak = 0
    try:
        import resource
        peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if os.sys.platform == "darwin" else 1024))
    except ImportError:
        pass
    row = dict(timestamp=datetime.now(UTC).isoformat(), trace_id=context["trace_id"], span_id=span_id,
        parent_span_id=parent, request_id=context.get("request_id"), job_id=context.get("job_id"),
        tenant_id=context.get("tenant_id"), component="observability", severity="ERROR" if failed else "INFO",
        error_category="execution_exception" if failed else None, duration_s=round(duration, 6),
        event=event, name=name, tool=tool, peak_rss_bytes=peak)
    path = context.get("path")
    if path:
        try:
            # One bounded append per record. Workers have only their private job folder.
            data = (json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n").encode()
            flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
            with LOCK:
                fd = os.open(path, flags, 0o600)
                try:
                    if os.fstat(fd).st_size + len(data) <= LIMIT:
                        os.write(fd, data)
                    else:
                        WRITE_FAILURES += 1
                finally:
                    os.close(fd)
        except (OSError, ValueError):
            WRITE_FAILURES += 1
    if context.get("stdout", True):
        emit(row)


def _record(*args, **kwargs):
    global WRITE_FAILURES
    try:
        _record_impl(*args, **kwargs)
    except Exception:
        # Observability cannot create a new scientific retry or interrupt settlement.
        WRITE_FAILURES += 1


@contextmanager
def span(name, *, context=None, tool=None):
    context = context or CONTEXT.get()
    if not context or name not in NAMES:
        yield
        return
    parent, identifier, start = context.get("span_id"), uuid.uuid4().hex[:16], time.perf_counter()
    token = CONTEXT.set(context | {"span_id": identifier})
    failed = False
    _record(context, name, identifier, parent, "start", tool=tool)
    try:
        yield
    except BaseException:
        failed = True
        raise
    finally:
        _record(context, name, identifier, parent, "end", time.perf_counter() - start, failed, tool)
        CONTEXT.reset(token)


def job_context(folder, owner, job_id):
    request_id = (CONTEXT.get() or {}).get("request_id")
    if not request_id:
        records = read_spans(folder / "telemetry.jsonl")
        request_id = records[0]["request_id"] if records else None
    return dict(trace_id=job_id, job_id=job_id, tenant_id=hashlib.sha256(owner.encode()).hexdigest(),
                path=str(folder / "telemetry.jsonl"), stdout=True,
                request_id=request_id)


def worker_environment():
    context = CONTEXT.get()
    return {"BLACKGRID_TRACE_CONTEXT": json.dumps(context | {"stdout": False})} if context else {}


def observed(name):
    """Preserve function arguments/results/exceptions; instrumentation never reads payloads."""
    def decorate(fn):
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            context = CONTEXT.get()
            if not context and os.environ.get("BLACKGRID_TRACE_CONTEXT"):
                try:
                    context = json.loads(os.environ["BLACKGRID_TRACE_CONTEXT"])
                except ValueError:
                    context = None
            tool = None
            if name == "tool_call":
                from blackgrid.operations.api_tools import CATALOG
                call = kwargs.get("call", args[4] if len(args) > 4 else {})
                if isinstance(call, dict) and call.get("tool") in CATALOG:
                    tool = call["tool"]
            with span(name, context=context, tool=tool):
                return fn(*args, **kwargs)
        return wrapped
    return decorate
