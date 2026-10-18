"""LLM provider adapters: deterministic mock (default), OpenRouter (live, gated), and replay.

Only aggregate statistics, the task text, and tool descriptions are ever placed in prompts. Raw
events, node identifiers, and answer keys never are. The API key is read from the environment or
a local `.env` file and is never written to prompts, traces, logs, or artifacts.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from blackgrid.budget import FREE, Pricing

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
KEY_NAMES = ("OPEN_ROUTER_API_KEY", "OPENROUTER_API_KEY")


class ProviderError(RuntimeError):
    """The provider call failed (network, HTTP, or malformed response)."""


class PricingUnavailable(RuntimeError):
    """Current pricing could not be confirmed, so paid execution is disabled."""


@dataclass(frozen=True)
class Completion:
    text: str
    prompt_tokens: int
    completion_tokens: int
    reported_usd: float | None
    model: str
    provider: str


class Provider(Protocol):
    name: str
    model: str

    def pricing(self) -> Pricing: ...

    def complete(self, role: str, payload: dict, messages: list[dict], max_tokens: int) -> Completion: ...


def prompt_sha256(messages: list[dict]) -> str:
    return hashlib.sha256(json.dumps(messages, sort_keys=True).encode("utf-8")).hexdigest()


# --- Secrets ------------------------------------------------------------------------------------


def load_env_file(path: Path) -> None:
    """Minimal .env reader: KEY=VALUE lines; existing environment variables win."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip().removeprefix("export ").strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def api_key_from_env() -> str | None:
    for name in KEY_NAMES:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


# --- Mock ---------------------------------------------------------------------------------------


def _ev(payload: dict, field: str) -> object:
    return payload.get("evidence", {}).get(f"experiment_report.json#/{field}")


def _request(payload: dict) -> dict:
    request = payload.get("task", {}).get("request", {})
    return request if isinstance(request, dict) else {}


class MockProvider:
    """Deterministic stand-in for an LLM. Its behaviour is scripted and deliberately naive.

    The planner complies with whatever the request asks; the first-draft analyst over-reads raw
    modularity. Revisions with critic feedback return conservative, evidence-matched claims.
    This tests the plumbing and the critic's catch rate on *these scripted* mistakes only; it
    says nothing about how a real model behaves.
    """

    name = "mock"
    model = "mock-naive-v1"

    def __init__(self, script: dict[str, list[str]] | None = None) -> None:
        self.script = {role: list(texts) for role, texts in (script or {}).items()}

    def pricing(self) -> Pricing:
        return FREE

    def complete(self, role: str, payload: dict, messages: list[dict], max_tokens: int) -> Completion:
        if self.script.get(role):
            text = self.script[role].pop(0)
        elif role == "planner":
            text = json.dumps(self._plan(payload))
        elif role == "analyst":
            text = json.dumps(self._analyse(payload, revise=False))
        elif role == "reviser":
            text = json.dumps(self._analyse(payload, revise=True))
        else:
            raise ProviderError(f"mock has no behaviour for role {role!r}")
        prompt_chars = sum(len(m["content"]) for m in messages)
        return Completion(text=text, prompt_tokens=prompt_chars // 4 + 1, completion_tokens=len(text) // 4 + 1,
                          reported_usd=0.0, model=self.model, provider=self.name)

    @staticmethod
    def _plan(payload: dict) -> dict:
        method = _request(payload).get("method", "auto")
        if method not in ("auto", "louvain"):
            return {"decision": "run", "tool_calls": [{"tool": "community_test", "args": {"method": method}}],
                    "reason": "Using the method the user specified."}
        return {"decision": "run", "reason": "Profile, test against the null, then check sensitivity.",
                "tool_calls": [{"tool": "profile_graph", "args": {}},
                               {"tool": "community_test", "args": {"method": "louvain"}},
                               {"tool": "edge_removal_sensitivity", "args": {}}]}

    @staticmethod
    def _analyse(payload: dict, revise: bool) -> dict:
        q = _ev(payload, "primary/result/observed_statistic")
        mean = _ev(payload, "primary/result/null/mean")
        p = _ev(payload, "primary/result/p_value")
        base = "experiment_report.json#/primary/result/"
        if not isinstance(q, (int, float)) or not isinstance(mean, (int, float)) or not isinstance(p, (int, float)):
            return {"verdict": "abstain", "flags": [], "claims": []}
        if revise:
            verdict = _ev(payload, "verdict")
            return {
                "verdict": verdict,
                "flags": list(payload.get("flags", [])),
                "claims": [
                    {"text": f"Modularity Q = {q:.3f} versus a degree-preserving null mean of {mean:.3f} "
                             f"(p = {p:.3f}).",
                     "evidence_level": "descriptive",
                     "evidence": [base + "observed_statistic", base + "null/mean", base + "p_value"]},
                    {"text": f"Under the preregistered rule the verdict is '{verdict}' for this graph only.",
                     "evidence_level": "descriptive", "evidence": ["experiment_report.json#/verdict"]},
                ],
            }
        claims = [
            {"text": f"The network has strong community structure (modularity Q = {q:.3f}).",
             "evidence_level": "descriptive", "evidence": [base + "observed_statistic"]},
            {"text": f"Observed modularity exceeds the null mean of {mean:.3f} (p = {p:.3f}).",
             "evidence_level": "descriptive", "evidence": [base + "null/mean", base + "p_value"]},
        ]
        if _request(payload).get("claim_type") == "causal":
            claims.append({"text": "The highest-degree nodes cause the community structure.",
                           "evidence_level": "identified_causal", "evidence": [base + "observed_statistic"]})
        return {"verdict": "supported" if q > 0.3 else "not_supported", "flags": [], "claims": claims}


# --- OpenRouter (live) --------------------------------------------------------------------------


class OpenRouterProvider:
    """Live adapter. Pricing is fetched before any paid call; if it cannot be confirmed, nothing is sent."""

    name = "openrouter"

    def __init__(self, model: str, api_key: str, timeout_s: float = 60.0) -> None:
        self.model = model
        self._key = api_key  # never logged
        self.timeout_s = timeout_s
        self._pricing: Pricing | None = None

    def __repr__(self) -> str:  # keep the key out of any accidental repr
        return f"OpenRouterProvider(model={self.model!r})"

    def pricing(self) -> Pricing:
        if self._pricing is None:
            try:
                with urllib.request.urlopen(f"{OPENROUTER_BASE}/models", timeout=self.timeout_s) as resp:
                    models = json.loads(resp.read().decode("utf-8")).get("data", [])
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                raise PricingUnavailable(f"could not fetch OpenRouter pricing: {exc}") from exc
            match = next((m for m in models if m.get("id") == self.model), None)
            if match is None:
                similar = sorted(m.get("id", "") for m in models if "claude" in m.get("id", ""))[:12]
                raise PricingUnavailable(f"model {self.model!r} not found on OpenRouter; e.g. {similar}")
            try:
                prompt = float(match["pricing"]["prompt"])
                completion = float(match["pricing"]["completion"])
            except (KeyError, TypeError, ValueError) as exc:
                raise PricingUnavailable(f"pricing missing for {self.model!r}") from exc
            if prompt < 0 or completion < 0:
                raise PricingUnavailable(f"pricing for {self.model!r} is not a fixed per-token price")
            self._pricing = Pricing(model=self.model, prompt_usd_per_token=prompt,
                                    completion_usd_per_token=completion, source=f"{OPENROUTER_BASE}/models",
                                    fetched_utc=datetime.now(UTC).isoformat())
        return self._pricing

    def complete(self, role: str, payload: dict, messages: list[dict], max_tokens: int) -> Completion:
        body = json.dumps({"model": self.model, "messages": messages, "max_tokens": max_tokens,
                           "temperature": 0, "usage": {"include": True}}).encode("utf-8")
        request = urllib.request.Request(
            f"{OPENROUTER_BASE}/chat/completions", data=body, method="POST",
            headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json",
                     "X-Title": "BLACKGRID Sprint 1"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ProviderError(f"OpenRouter HTTP {exc.code}") from None  # body may echo request; not kept
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise ProviderError(f"OpenRouter request failed: {type(exc).__name__}") from None
        try:
            text = data["choices"][0]["message"]["content"] or ""
            usage = data.get("usage", {})
            return Completion(text=text, prompt_tokens=int(usage.get("prompt_tokens", 0)),
                              completion_tokens=int(usage.get("completion_tokens", 0)),
                              reported_usd=float(usage["cost"]) if usage.get("cost") is not None else None,
                              model=str(data.get("model", self.model)), provider=self.name)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("OpenRouter returned a malformed response") from exc


# --- Replay -------------------------------------------------------------------------------------


class ReplayMismatch(RuntimeError):
    """The replayed run asked for a different prompt than the recorded one."""


class ReplayProvider:
    """Replays the recorded responses of an earlier run, in order, verifying each prompt hash."""

    name = "replay"

    def __init__(self, trace_path: Path) -> None:
        self.entries = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line]
        self.model = self.entries[0]["model"] if self.entries else "replay"
        self._next = 0

    def pricing(self) -> Pricing:
        return FREE  # replay spends nothing

    def complete(self, role: str, payload: dict, messages: list[dict], max_tokens: int) -> Completion:
        if self._next >= len(self.entries):
            raise ReplayMismatch("the recorded trace has no further responses")
        entry = self.entries[self._next]
        self._next += 1
        if entry["role"] != role or entry["prompt_sha256"] != prompt_sha256(messages):
            raise ReplayMismatch(f"call {self._next}: recorded {entry['role']} prompt differs from this run")
        return Completion(text=entry["response"], prompt_tokens=entry["prompt_tokens"],
                          completion_tokens=entry["completion_tokens"], reported_usd=0.0,
                          model=entry["model"], provider=self.name)
