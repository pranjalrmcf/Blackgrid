"""Session 6: registered prediction tools and the prospective forecast workflow.

Tools (SPRINT_06.md §8) take strict typed arguments. None of them accepts a cutoff, a candidate list,
code or a budget: the planner can pick a supported task/method only. Test aggregates are readable
only from a *completed, frozen* evaluation, and test labels are never readable. Pair rankings are
local artifacts; tool outputs to any planner are aggregates.

`forecast()` is the free mock path: a scripted plan (temporal_profile -> link_prediction ->
prediction_compare), deterministic scoring, templated claims checked by `pred-critic-v1`.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import ValidationError

from blackgrid.contracts import Contract
from blackgrid.prediction import PREDICTION_VERSION
from blackgrid.prediction import scores as S
from blackgrid.prediction.claims import PRED_CRITIC_VERSION, check
from blackgrid.prediction.features import attach_labels, build_snapshot
from blackgrid.prediction.model import fit
from blackgrid.prediction.temporal import Event, Task, boundaries, candidate_count, candidates, history, \
    horizon_labels

TOP_LOCAL = 100
FORBIDDEN = ("label", "truth", "answer", "sealed", "cutoff", "candidate", "code", "exec", "budget")


class PredictionToolRejected(ValueError):
    pass


class TemporalProfileArgs(Contract):
    pass


class LinkPredictionArgs(Contract):
    task: Literal["new_pair", "repeat_pair"]
    method: str = "selected"  # "selected" = the frozen prediction-v1 temporal choice for this task


class PredictionCompareArgs(Contract):
    task: Literal["new_pair", "repeat_pair"]
    split: Literal["validation", "test"] = "validation"


TOOLS = {"temporal_profile": TemporalProfileArgs, "link_prediction": LinkPredictionArgs,
         "prediction_compare": PredictionCompareArgs}


def parse(request: object) -> tuple[str, Contract]:
    text = json.dumps(request, sort_keys=True, default=str).lower()
    if any(word in text for word in FORBIDDEN):
        raise PredictionToolRejected("request references labels, cutoffs, candidates, code or budgets; not allowed")
    if not isinstance(request, dict) or set(request) - {"tool", "args"} or request.get("tool") not in TOOLS:
        raise PredictionToolRejected("unknown or malformed prediction tool request")
    try:
        return request["tool"], TOOLS[request["tool"]].model_validate(request.get("args") or {})
    except ValidationError as exc:
        raise PredictionToolRejected(f"invalid arguments: {exc.errors()[0]['msg']}") from exc


class PredictionTools:
    """Bound to one event table and one frozen evaluation folder (trusted inputs)."""

    def __init__(self, events: list[Event], evaluation: Path) -> None:
        self.events = events
        self.evaluation = evaluation
        self.b = boundaries(events)
        self.horizon = self.b[1] - self.b[0]
        self.cutoff = self.b[10]  # prospective: all validated history; fixed by the system, not the planner
        self.selection = json.loads((evaluation / "selection.json").read_text(encoding="utf-8"))["selection"]

    def call(self, request: object) -> dict:
        name, args = parse(request)
        return getattr(self, name)(args)

    def temporal_profile(self, args: TemporalProfileArgs) -> dict:
        hist = history(self.events, self.cutoff)
        return {"cutoff": self.cutoff, "horizon_s": self.horizon, "history_events": hist.events,
                "history_nodes": len(hist.nodes), "history_pairs": len(hist.pair_count),
                "first_event": self.b[0], "candidates": {t: candidate_count(hist, t) for t in ("new_pair", "repeat_pair")}}

    def resolve_method(self, task: Task, method: str) -> str:
        name = self.selection[task]["temporal"] if method == "selected" else method
        allowed = {m.name for m in S.methods_for(task)} | {self.selection[task]["temporal"]}
        if name not in allowed:
            raise PredictionToolRejected(f"method {name!r} is not registered for {task}")
        return name

    def link_prediction(self, args: LinkPredictionArgs, local_out: Path | None = None) -> dict:
        task, name = args.task, self.resolve_method(args.task, args.method)
        hist = history(self.events, self.cutoff)
        refit = None
        if name.startswith("logistic_C"):  # frozen configuration, refitted on all labelled history (no tuning)
            snaps = []
            for i in range(2, 10):
                h = history(self.events, self.b[i])
                snaps.append(attach_labels(build_snapshot(h, task, self.horizon), h,
                                           horizon_labels(self.events, h, self.b[i + 1])))
            model = fit(task, snaps, float(name.removeprefix("logistic_C")))
            snap = build_snapshot(hist, task, self.horizon)
            scores_ = model.score(snap)
            refit = {"rows": sum(s.size for s in snaps), "converged": model.converged}
        else:
            snap = build_snapshot(hist, task, self.horizon, extra=False)
            scores_ = snap.columns[name]
        order = np.lexsort((snap.tiebreak, -scores_))[:TOP_LOCAL]
        pairs = list(candidates(hist, task))
        if local_out is not None:  # local only: never sent to a model or exported
            local_out.write_text(json.dumps([{"rank": r + 1, "pair": list(pairs[j]), "score": float(scores_[j])}
                                             for r, j in enumerate(order)], indent=1), encoding="utf-8")
        return {"task": task, "method": name, "cutoff": self.cutoff, "horizon_s": self.horizon,
                "horizon_days": round(self.horizon / 86400, 2),
                "candidates": snap.size, "candidate_policy": "complete known-node universe",
                "scores": "uncalibrated ranking scores", "refit": refit,
                "top_score_ties": int(np.sum(scores_ == scores_[order[0]])) if snap.size else 0}

    def prediction_compare(self, args: PredictionCompareArgs) -> dict:
        val = json.loads((self.evaluation / "validation.json").read_text(encoding="utf-8"))[args.task]["table"]
        if args.split == "validation":
            # Paths name the metric (".../methods/<m>/mean_average_precision") so a cited AP is checkable (D-075).
            return {"task": args.task, "split": "validation",
                    "methods": {k: {"mean_average_precision": v["mean_ap"]} for k, v in val.items()},
                    "selection": self.selection[args.task]}
        if not (self.evaluation / "predictions_manifest.json").is_file() or \
                not (self.evaluation / "test_evaluation.json").is_file():
            raise PredictionToolRejected("test aggregates exist only after a frozen, completed evaluation")
        test = json.loads((self.evaluation / "test_evaluation.json").read_text(encoding="utf-8"))["test"][args.task]
        return {"task": args.task, "split": "test", "selection": self.selection[args.task],
                "cutoffs": {c: {m: {"average_precision": r["average_precision"]} for m, r in cut["methods"].items()}
                            for c, cut in test["cutoffs"].items()},
                "prevalence": {c: cut["manifest"]["prevalence"] for c, cut in test["cutoffs"].items()},
                "mean_ap_difference": test.get("mean_ap_difference")}


def _flatten(prefix: str, value: object, out: dict) -> dict:
    if isinstance(value, dict):
        for k, v in value.items():
            _flatten(f"{prefix}/{k}", v, out)
    elif isinstance(value, (int, float, str, bool)) or value is None:
        out[prefix] = value
    return out


def forecast(events: list[Event], evaluation: Path, output: Path, task: Task, method: str = "selected",
             data_sha256: str = "unknown") -> Path:
    """Prospective forecast (no realized labels yet) with evidence-linked, checked claims."""
    output = output.resolve()
    tools = PredictionTools(events, evaluation)
    plan = [{"tool": "temporal_profile", "args": {}}, {"tool": "link_prediction", "args": {"task": task, "method": method}},
            {"tool": "prediction_compare", "args": {"task": task, "split": "test"}}]
    for step in plan:  # validate the whole plan before any artifact is written
        name, checked = parse(step)
        if name == "link_prediction":
            tools.resolve_method(checked.task, checked.method)
    output.mkdir(parents=True, exist_ok=False)
    profile = tools.call(plan[0])
    name, args = parse(plan[1])
    result = tools.link_prediction(args, local_out=output / "local_ranking.json")
    compare = tools.call(plan[2])
    data = {"profile": profile, "prediction": result, "compare": compare}
    evidence = _flatten("forecast.json#", data, {})
    scope = {"task": task, "cutoff": tools.cutoff, "horizon_s": tools.horizon,
             "candidate_policy": "complete known-node universe", "split": "prospective", "method": result["method"]}
    m = result["method"]
    days = result["horizon_days"]
    test_scope = scope | {"split": "test"}
    claims = [
        {"text": f"Prospective {task} forecast: {result['candidates']} known-node candidate pairs ranked by {m} "
                 f"for the next {days} days after the last observed event; scores are uncalibrated rankings.",
         "evidence": ["forecast.json#/prediction/candidates", "forecast.json#/prediction/horizon_days"],
         "scope": scope},
    ]
    ap = {c: {k: v["average_precision"] for k, v in cut.items()} for c, cut in compare["cutoffs"].items()}
    if m in ap.get("b8", {}) and ap["b8"][m] is not None and ap["b9"].get(m) is not None:
        claims.append({"text": f"In the frozen prediction-v1 test, {m} had average precision {ap['b8'][m]:.4f} (b8) and "
                               f"{ap['b9'][m]:.4f} (b9), against prevalence {compare['prevalence']['b8']:.5f} and "
                               f"{compare['prevalence']['b9']:.5f}.",
                       "evidence": [f"forecast.json#/compare/cutoffs/b8/{m}/average_precision",
                                    f"forecast.json#/compare/cutoffs/b9/{m}/average_precision",
                                    "forecast.json#/compare/prevalence/b8", "forecast.json#/compare/prevalence/b9"],
                       "scope": test_scope})
    claims.append({"text": "Pairs involving people first seen after the cutoff are excluded; this forecast says nothing "
                           "about them, and no realized outcome exists yet.",
                   "evidence": ["forecast.json#/prediction/candidate_policy"], "scope": scope})
    decisions = []
    for claim in claims:
        expected = test_scope if claim["scope"].get("split") == "test" else scope
        reasons = check(claim, evidence, expected)
        decisions.append({"claim": claim, "accepted": not reasons, "reasons": reasons})
    record = {"version": PREDICTION_VERSION, "critic": PRED_CRITIC_VERSION, "created_utc": datetime.now(UTC).isoformat(),
              "mode": "mock (scripted plan, deterministic scoring, no LLM call)", "usd": 0.0, "data_sha256": data_sha256,
              "evaluation": str(evaluation.name), "plan": plan, **data, "decisions": decisions,
              "local_ranking": "local_ranking.json (local only; never exported)"}
    path = output / "forecast.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (output / "forecast.sha256").write_text(hashlib.sha256(path.read_bytes()).hexdigest() + "\n", encoding="utf-8")
    return output
