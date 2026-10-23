"""Registered synthetic Beta–Bernoulli research decisions; no real-graph VOI."""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Callable, Literal

from pydantic import Field, StrictBool
from scipy.stats import beta, betabinom

from blackgrid.contracts import Contract, NonEmpty


class BeliefSpec(Contract):
    generator: NonEmpty = "independent-bernoulli-tasks-v1"
    success_rule: NonEmpty = "binary task success, fixed configuration"
    alpha: float = Field(default=1, gt=0, allow_inf_nan=False)
    beta: float = Field(default=1, gt=0, allow_inf_nan=False)

    @property
    def identity(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()


class Observation(Contract):
    identity: NonEmpty
    observation_id: NonEmpty
    action: Literal["A", "B"]
    success: StrictBool
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Objective(Contract):
    identity: Literal["future-task-success-v1"] = "future-task-success-v1"
    cost: float = Field(default=0.02, ge=0, allow_inf_nan=False)
    max_steps: int = Field(default=10, ge=0, le=10)


def posterior(spec: BeliefSpec, observations: list[Observation], action: str) -> tuple[float, float]:
    if action not in ("A", "B"):
        raise ValueError("unregistered action")
    seen = set()
    a, b = spec.alpha, spec.beta
    for obs in observations:
        if obs.identity != spec.identity or obs.observation_id in seen:
            raise ValueError("wrong belief identity or duplicate observation")
        seen.add(obs.observation_id)
        if obs.action == action:
            a += int(obs.success)
            b += int(not obs.success)
    return a, b


def summarize(spec: BeliefSpec, observations: list[Observation]) -> dict:
    result = {}
    for action in ("A", "B"):
        a, b = posterior(spec, observations, action)
        result[action] = {"alpha": a, "beta": b, "mean": a / (a + b),
                          "credible_interval_95": list(map(float, beta.ppf([0.025, 0.975], a, b))),
                          "predictive_block_10": list(map(float, betabinom.pmf(range(11), 10, a, b)))}
    return {"identity": spec.identity, "spec": spec.model_dump(), "observations": len(observations),
            "target": "success rate across independent simulated tasks", "methods": result,
            "interval_type": "Bayesian credible interval under registered model"}


def decide(spec: BeliefSpec, observations: list[Observation], objective: Objective,
           *, feasible: tuple[str, ...] = ("A", "B")) -> dict:
    if set(feasible) - {"A", "B"}:
        raise ValueError("unregistered experiment")
    states = {k: posterior(spec, observations, k) for k in ("A", "B")}
    means = {k: a / (a + b) for k, (a, b) in states.items()}
    terminal = max(means, key=means.get)  # stable A-first tie
    stop_value = means[terminal]
    rows = []
    for k, (a, b) in states.items():
        other = means["B" if k == "A" else "A"]
        expected = means[k] * max((a + 1) / (a + b + 1), other)
        expected += (1 - means[k]) * max(a / (a + b + 1), other)
        evsi = max(0.0, expected - stop_value)
        allowed = k in feasible and len(observations) < objective.max_steps
        rows.append({"action": k, "evsi": evsi, "cost": objective.cost,
                     "net_value": evsi - objective.cost, "feasible": allowed,
                     "rejection": None if allowed else "step budget exhausted or action unavailable"})
    best = max((r for r in rows if r["feasible"]), key=lambda r: r["net_value"], default=None)
    action = best["action"] if best and best["net_value"] > 1e-12 else "stop"
    return {"action": action, "terminal_method": terminal, "stop_value": stop_value,
            "candidates": rows, "objective": objective.model_dump(), "steps": len(observations),
            "scope": "synthetic independent tasks only; exact myopic EVSI",
            "reason": "positive net value" if action != "stop" else "no feasible positive net value"}


def sensitivity(observations: list[Observation], objective: Objective) -> dict:
    rows = []
    for prior in (0.5, 1.0, 2.0):
        spec = BeliefSpec(alpha=prior, beta=prior)
        obs = [o.model_copy(update={"identity": spec.identity}) for o in observations]
        for cost in (0.01, 0.02, 0.04):
            d = decide(spec, obs, objective.model_copy(update={"cost": cost}))
            rows.append({"prior": prior, "cost": cost, "action": d["action"],
                         "terminal_method": d["terminal_method"]})
    return {"rows": rows, "stable_action": len({r["action"] for r in rows}) == 1,
            "stable_terminal": len({r["terminal_method"] for r in rows}) == 1}


class ObservationStore:
    """Trusted numerical observations only. Unique IDs make replay updates idempotent."""

    def __init__(self, path: Path, *, read_only: bool = False):
        self.path = path
        self.read_only = read_only
        if read_only:
            return
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS observations (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")

    def add(self, observation: Observation) -> bool:
        if self.read_only:
            raise ValueError("read-only observation evidence")
        payload = observation.model_dump_json()
        with sqlite3.connect(self.path) as db:
            old = db.execute("SELECT payload FROM observations WHERE id=?", (observation.observation_id,)).fetchone()
            if old:
                if old[0] != payload:
                    raise ValueError("observation ID reused with different evidence")
                return False
            db.execute("INSERT INTO observations VALUES (?, ?)", (observation.observation_id, payload))
        return True

    def read(self) -> list[Observation]:
        with sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True) if self.read_only else sqlite3.connect(self.path) as db:
            return [Observation.model_validate_json(r[0]) for r in
                    db.execute("SELECT payload FROM observations ORDER BY rowid")]


def loop(spec: BeliefSpec, objective: Objective, observe: Callable[[str, int], Observation],
         store: ObservationStore, guard: Callable[[], None] = lambda: None) -> list[dict]:
    """Source is a trusted registered tool, never arbitrary model-provided code."""
    trace = []
    while True:
        guard()
        observations = store.read()
        d = decide(spec, observations, objective)
        trace.append(d)
        if d["action"] == "stop":
            return trace
        # A fixed ten-step bound applies even if a malicious source repeats an ID.
        obs = observe(d["action"], len(observations))
        if obs.identity != spec.identity or obs.action != d["action"]:
            raise ValueError("outcome source returned incompatible evidence")
        if not store.add(obs):
            raise ValueError("outcome source repeated an observation")


def predictive_check(a: float, b: float, successes: int, trials: int) -> dict:
    if not (math.isfinite(a) and math.isfinite(b) and a > 0 and b > 0 and 0 <= successes <= trials):
        raise ValueError("invalid predictive check")
    tail = min(1.0, 2 * min(float(betabinom.cdf(successes, trials, a, b)),
                          float(betabinom.sf(successes - 1, trials, a, b))))
    return {"block_successes": successes, "trials": trials, "two_sided_predictive_tail": tail,
            "limitation": "predictive misfit: stop" if tail < 0.01 else None}
