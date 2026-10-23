"""Frozen offline Sprint 7 comparisons. Simulator truth stays in trusted evaluation."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import platform
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy.special import expit
from scipy.stats import beta, betabinom
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from blackgrid.analysis.decisions import (BeliefSpec, Objective, Observation, ObservationStore, decide,
                                         loop, predictive_check, sensitivity, summarize)
from blackgrid.analysis.reliability import (CalibrationPartition, diagnostics, disagreement, fit_sigmoid,
                                           interval_eligibility, paired_bootstrap, validate_partitions)
from blackgrid.analysis.causal import CausalReview, collegemsg_refusal, identify
from blackgrid.prediction.suite import peak_memory_bytes

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = ROOT / "protocols" / "sprint07_decisions_v1.md"
POLICIES = ("stop", "fixed", "random", "greedy", "evsi")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, indent=2, sort_keys=True, allow_nan=False)
        f.write("\n")


def observation(spec: BeliefSpec, action: str, i: int, success: bool, prefix: str) -> Observation:
    payload = json.dumps([prefix, action, i, success], separators=(",", ":"))
    return Observation(identity=spec.identity, action=action, observation_id=f"{prefix}-{action}-{i}",
                       success=success, evidence_sha256=hashlib.sha256(payload.encode()).hexdigest())


class Guard:
    """Cooperative trusted-tool limits. Not an OS sandbox or preemptive allocator."""
    def __init__(self, output: Path):
        self.output = output
        self.start = self.tool_start = time.monotonic()

    def check(self):
        if (self.output / "CANCEL").exists():
            raise InterruptedError("cancelled at trusted operation boundary")
        now = time.monotonic()
        if now - self.start > 3600 or now - self.tool_start > 120:
            raise TimeoutError("registered wall-time budget exhausted")
        peak = peak_memory_bytes()
        if peak is None:
            raise RuntimeError("memory measurement unavailable; numerical work stopped")
        if peak > 2 * 1024**3:
            raise MemoryError("2 GiB process memory budget exceeded")

    def begin(self):
        self.tool_start = time.monotonic()
        self.check()


def policy_comparison(guard: Guard) -> dict:
    rows = []
    for seed in range(71000, 71100):
        guard.check()
        rng = np.random.default_rng(seed)
        truth = dict(zip(("A", "B"), rng.uniform(size=2)))
        streams = {a: rng.random(10) < truth[a] for a in truth}
        terminal_draw = rng.random()
        for policy in POLICIES:
            spec, objective, obs = BeliefSpec(), Objective(), []
            counts = {"A": 0, "B": 0}
            random_policy = np.random.default_rng(seed + 100000)
            for step in range(10):
                d = decide(spec, obs, objective)
                action = {"stop": "stop", "fixed": ("A", "B")[step % 2],
                          "random": str(random_policy.choice(["A", "B"])),
                          "greedy": d["terminal_method"], "evsi": d["action"]}[policy]
                if action == "stop":
                    break
                success = bool(streams[action][counts[action]])
                counts[action] += 1
                obs.append(observation(spec, action, step, success, f"episode-{seed}"))
            method = decide(spec, obs, objective)["terminal_method"]
            cost = len(obs) * objective.cost
            rows.append({"seed": seed, "policy": policy, "steps": len(obs),
                         "expected_utility": truth[method] - cost,
                         "realized_utility": float(terminal_draw < truth[method]) - cost,
                         "regret": max(truth.values()) - truth[method], "status": "completed"})
    summary = {p: {metric: float(np.mean([r[metric] for r in rows if r["policy"] == p]))
                   for metric in ("steps", "expected_utility", "realized_utility", "regret")} for p in POLICIES}
    return {"episodes": 100, "rows": rows, "policies": summary, "failure_rate": 0,
            "useful_answer_coverage": 1.0, "scope": "independent Bernoulli task simulator, not graph ML efficacy"}


def bayesian_checks(guard: Guard) -> dict:
    rows = []
    for prior in (0.5, 1.0, 2.0):
        coverage, predictive_coverage, prior_counts, posterior_counts = [], [], [], []
        for seed in range(72000, 72200):
            guard.check()
            rng = np.random.default_rng(seed)
            theta = rng.beta(prior, prior)
            s = int(rng.binomial(20, theta))
            a, b = prior+s, prior+20-s
            lo, hi = beta.ppf([0.025, 0.975], a, b)
            coverage.append(bool(lo <= theta <= hi))
            future = int(rng.binomial(10, theta))
            plo, phi = betabinom.ppf([0.025, 0.975], 10, a, b)
            predictive_coverage.append(bool(plo <= future <= phi))
            prior_counts.append(s)
            posterior_counts.append(future)
        rows.append({"prior": [prior, prior], "replicates": 200,
                     "credible_coverage": float(np.mean(coverage)),
                     "predictive_block_coverage": float(np.mean(predictive_coverage)),
                     "prior_predictive_counts": prior_counts, "held_out_block_counts": posterior_counts})
    return {"rows": rows, "limitation": "prior-predictive simulation coverage; no universal coverage guarantee"}


def calibration_comparison(guard: Guard) -> dict:
    rows, differences, agreements = [], [], []
    for seed in range(73000, 73030):
        guard.begin()
        rng = np.random.default_rng(seed)
        x = rng.normal(size=(435, 1))
        truth = expit(-2 + 1.2*x[:, 0])
        # Independent temporal event outcomes, every candidate retained in each period.
        labels = [rng.random(435) < truth for _ in range(5)]
        scaler = StandardScaler().fit(x)
        model = LogisticRegression(C=1, max_iter=300).fit(scaler.transform(x), labels[0])
        if int(model.n_iter_.max()) >= 300:
            raise ValueError("registered base model did not converge")
        score = model.decision_function(scaler.transform(x))
        parts = [CalibrationPartition(role, i, i+1, score.copy(), labels[i]) for i, role in
                 enumerate(("train", "selection", "fit", "assessment", "test"))]
        validate_partitions(parts)
        calibrator = fit_sigmoid(parts[2])
        p = calibrator.predict_proba(score[:, None])[:, 1]
        entry = {"seed": seed, "candidates_per_period": 435, "periods": {}}
        for part in (parts[3], parts[4]):
            raw, calibrated = diagnostics(expit(score), part.labels), diagnostics(p, part.labels)
            entry["periods"][part.role] = {"raw": raw, "sigmoid": calibrated,
                                          "score_extrapolation": False,
                                          "drift_prevalence_from_fit": float(part.labels.mean()-labels[2].mean())}
        differences.append(entry["periods"]["test"]["sigmoid"]["brier"] -
                           entry["periods"]["test"]["raw"]["brier"])
        agreements.append(disagreement({"raw": score, "sigmoid": p}, np.arange(len(p))))
        rows.append(entry)
    guard.begin()
    coverage = []
    for seed in range(74100, 74200):
        guard.check()
        x = np.random.default_rng(seed).normal(size=30)
        lo, hi = paired_bootstrap(x, seed=seed, independent=True)["interval"]
        coverage.append(lo <= 0 <= hi)
    return {"graphs": 30, "rows": rows, "disagreement": agreements,
            "paired_test_brier": paired_bootstrap(differences, independent=True),
            "bootstrap_behavior_check": {"replicates": 100, "coverage": float(np.mean(coverage)),
                                         "distribution": "independent normal graph summaries; true mean zero"},
            "real_data_interval": interval_eligibility("time_window", 2),
            "probability_display": False, "scope": "synthetic event generator only"}


def causal_comparison(guard: Guard) -> dict:
    review = CausalReview(treatment="T", outcome="Y", unit="independent synthetic graph",
                          population="registered synthetic distribution", edges=(("X", "Y"), ("T", "Y")),
                          adjustment=("X",), observed=("T", "Y", "X"), provenance="registered linear SCM",
                          synthetic=True, time_order=True, consistency=True, positivity=True,
                          no_hidden_confounding=True, no_selection_bias=True, no_interference=True,
                          measurement_valid=True)
    gate = identify(review)
    if gate["verdict"] != "simulated intervention only":
        raise ValueError("registered causal example not identified")
    rows = []
    for seed in range(75000, 75100):
        guard.check()
        rng = np.random.default_rng(seed)
        x = rng.normal(size=500)
        t = rng.binomial(1, 0.5, size=500)
        y = 2*t + 1.5*x + rng.normal(size=500)
        naive = float(y[t == 1].mean() - y[t == 0].mean())
        coef = np.linalg.lstsq(np.column_stack([np.ones(500), t, x]), y, rcond=None)[0]
        rows.append({"seed": seed, "naive": naive, "adjusted": float(coef[1])})
    metrics = {name: {"bias": float(np.mean([r[name]-2 for r in rows])),
                      "rmse": float(np.sqrt(np.mean([(r[name]-2)**2 for r in rows])))}
               for name in ("naive", "adjusted")}
    refusals = {key: identify(review.model_copy(update={key: False}))
                for key in ("positivity", "no_hidden_confounding", "no_interference")}
    return {"gate": gate, "known_ate": 2, "rows": rows, "metrics": metrics,
            "refusals": refusals, "collegemsg": collegemsg_refusal(),
            "limitation": "randomized toy example; no evidence of real-world causal influence"}


def beliefs_match(actual: dict, recorded: dict, profile: str | None = None) -> bool:
    if profile is None:
        return actual == recorded
    if profile != "api-beliefs-portability-v1":
        raise ValueError("unknown belief verification profile")
    # Compare on a copy only. Source artifacts and all non-derived fields stay exact.
    comparison = json.loads(json.dumps(actual))
    try:
        for method in ("A", "B"):
            for field, size in (("mean", 1), ("credible_interval_95", 2), ("predictive_block_10", 11)):
                left, right = actual["methods"][method][field], recorded["methods"][method][field]
                lefts, rights = ([left], [right]) if size == 1 else (left, right)
                if not isinstance(lefts, list) or not isinstance(rights, list) or len(lefts) != size or len(rights) != size:
                    return False
                for a, b in zip(lefts, rights):
                    if (type(a) is not float or type(b) is not float or not math.isfinite(a) or not math.isfinite(b)
                            or not 0 <= a <= 1 or not 0 <= b <= 1
                            or abs(a-b) > 1e-12 + 1e-12 * max(abs(a), abs(b))):
                        return False
                comparison["methods"][method][field] = right
    except (KeyError, TypeError):
        return False
    def exact(left, right):
        if type(left) is not type(right):
            return False
        if isinstance(left, dict):
            return left.keys() == right.keys() and all(exact(left[key], right[key]) for key in left)
        if isinstance(left, list):
            return len(left) == len(right) and all(exact(a, b) for a, b in zip(left, right))
        return left == right
    return exact(comparison, recorded)


def verify(output: Path, *, numerical_profile: str | None = None) -> dict:
    manifest = json.loads((output / "sprint7_manifest.json").read_text(encoding="utf-8"))
    required = {"freeze.json", "belief.sqlite", "beliefs.json", "decisions.json", "predictive_check.json",
                "policy_comparison.json", "bayesian_checks.json", "reliability.json", "causal.json", "summary.json"}
    if manifest["status"] != "completed" or not required <= manifest["artifacts"].keys():
        raise ValueError("incomplete scientific evidence")
    for name, expected in manifest["artifacts"].items():
        path = (output / name).resolve()
        if not path.is_relative_to(output.resolve()) or digest(path) != expected:
            raise ValueError("artifact integrity failure")
    spec = BeliefSpec()
    store = ObservationStore(output / "belief.sqlite", read_only=True)
    actual = summarize(spec, store.read())
    recorded = json.loads((output / "beliefs.json").read_text(encoding="utf-8"))
    if not beliefs_match(actual, recorded, numerical_profile):
        raise ValueError("belief evidence mismatch")
    return {"status": "verified", "artifacts": len(manifest["artifacts"]), "usd": 0,
            "observations": len(store.read()), "replay": "read-only verification; no new outcomes",
            "numerical_profile": numerical_profile or "exact"}


def run(output: Path) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    guard = Guard(output)
    started = datetime.now(UTC).isoformat()
    source = {p.relative_to(ROOT).as_posix(): digest(p) for area in ("src", "tests", "configs")
              for p in (ROOT / area).rglob("*") if p.is_file() and p.suffix in (".py", ".json", ".html")}
    try:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                  text=True, check=True, timeout=10).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
                                    text=True, check=True, timeout=10).stdout)
    except (OSError, subprocess.SubprocessError):
        # Source exports and runtime images may have neither Git nor a checkout.
        # Keep source hashes above and report unavailable provenance explicitly.
        revision, dirty = None, None
    save(output / "freeze.json", {"version": "decisions-v1", "protocol_sha256": digest(PROTOCOL),
                                 "source_hashes": source, "source_revision": revision, "dirty": dirty,
                                 "lock_sha256": digest(ROOT / "uv.lock"), "objective": Objective().model_dump(),
                                 "python": platform.python_version(), "platform": platform.platform(),
                                 "dependencies": {k: importlib.metadata.version(k) for k in
                                                  ("numpy", "scipy", "scikit-learn", "pydantic")},
                                 "started_utc": started, "paid_usd": 0, "llm_calls": 0})
    attempts = []
    status, reason = "completed", None
    try:
        guard.begin()
        spec, objective = BeliefSpec(), Objective()
        store = ObservationStore(output / "belief.sqlite")
        rng = np.random.default_rng(70000)
        # One independent outcome stream per method; source owns truth.
        def observe(action, i):
            return observation(spec, action, i, bool(rng.random() < {"A": 0.65, "B": 0.45}[action]), "demo")
        trace = loop(spec, objective, observe, store, guard.check)
        beliefs = summarize(spec, store.read())
        save(output / "beliefs.json", beliefs)
        save(output / "decisions.json", {"trace": trace, "sensitivity": sensitivity(store.read(), objective),
                                         "real_forecast_voi": "unavailable: no experiment-outcome model",
                                         "scope": "simulated tasks only"})
        state_a = beliefs["methods"]["A"]
        check = predictive_check(state_a["alpha"], state_a["beta"], int(rng.binomial(10, 0.65)), 10)
        save(output / "predictive_check.json", check)
        if check["limitation"]:
            raise ValueError("posterior predictive misfit")
        for name, tool in (("policy_comparison", policy_comparison), ("bayesian_checks", bayesian_checks),
                           ("reliability", calibration_comparison), ("causal", causal_comparison)):
            guard.begin()
            t = time.monotonic()
            try:
                result = tool(guard)
                guard.check()
                save(output / f"{name}.json", result)
            except Exception:
                attempts.append({"tool": name, "status": "failed", "elapsed_s": time.monotonic()-t})
                raise
            attempts.append({"tool": name, "status": "completed", "elapsed_s": time.monotonic()-t})
        save(output / "summary.json", {"version": "decisions-v1", "status": "completed",
                                       "policy_comparison": result_summary(output, "policy_comparison", "policies"),
                                       "bootstrap": result_summary(output, "reliability", "paired_test_brier"),
                                       "causal": result_summary(output, "causal", "metrics"),
                                       "bayesian_optimization": "skipped: expensive-search gate unmet", "usd": 0})
    except Exception as exc:
        status = "cancelled" if isinstance(exc, InterruptedError) else "failed"
        # No raw inputs, exception payload or traceback in the sanitized failure record.
        reason = type(exc).__name__
    artifacts = {p.name: digest(p) for p in output.iterdir() if p.is_file() and p.name != "CANCEL"}
    save(output / "sprint7_manifest.json", {"status": status, "failure": reason, "artifacts": artifacts,
                                           "attempts": attempts, "elapsed_s": time.monotonic()-guard.start,
                                           "peak_memory_bytes": peak_memory_bytes(), "created_utc": started,
                                           "isolation": "trusted registered tools; cooperative limits; no OS sandbox",
                                           "usd": 0})
    if status == "completed":
        verify(output)
        from blackgrid.agent.research import ResearchTools, checked_claim
        tools = ResearchTools(output)
        evidence = {name: json.loads((output / name).read_text(encoding="utf-8")) for name in
                    ("beliefs.json", "decisions.json", "reliability.json", "causal.json")}
        checked = [checked_claim("posterior_mean_A", evidence["beliefs.json"]["methods"]["A"]["mean"], evidence),
                   checked_claim("next_action", evidence["decisions.json"]["trace"][-1]["action"], evidence),
                   checked_claim("brier_interval", evidence["reliability.json"]["paired_test_brier"]["interval"], evidence),
                   checked_claim("causal_verdict", evidence["causal.json"]["gate"]["verdict"], evidence)]
        save(output / "research_agent.json", {"mode": "mock", "claims": checked, "calls": [
            {"tool": name, "result": tools.call({"tool": name})} for name in
            ("reliability_audit", "belief_update", "experiment_decision", "causal_identification_check")]})
        # Standard console investigation wrapper, without entering the paid/LLM workflow.
        save(output / "investigation.json", {"family": "decisions", "status": status, "verdict": "synthetic only",
                                             "cost": {"mode": "mock", "actual_usd": 0, "llm_calls": 0}})
        save(output / "config.json", {"question": "Is another synthetic experiment worth its cost?"})
        from blackgrid.console.render import write_run_snapshot, write_index_snapshot
        write_run_snapshot(output.parent, output)
        write_index_snapshot(output.parent)
    return {"status": status, "failure": reason, "output": str(output), "attempts": attempts, "usd": 0}


def result_summary(output: Path, name: str, key: str):
    return json.loads((output / f"{name}.json").read_text(encoding="utf-8"))[key]
