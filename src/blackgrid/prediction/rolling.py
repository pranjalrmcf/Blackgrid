"""prediction-v2 rolling-origin evaluation (protocols/sprint06_prediction_v2.md). Run once; report everything.

Cutoffs are processed in time order. At test origin b_k the models are trained only on rows from
cutoffs b2..b(k-1) (label windows end by b_k); this origin's rows join the pool only afterwards.
Evaluation always uses the complete candidate universe. USD 0, no LLM.
"""
from __future__ import annotations

import hashlib
import json
import time
import warnings
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from blackgrid.prediction.fast import rank_metrics_np
from blackgrid.prediction.features import attach_labels, build_snapshot
from blackgrid.prediction.features_v2 import V2_COLUMNS, V2_REPEAT, add_v2_columns
from blackgrid.prediction.suite import _save, peak_memory_bytes
from blackgrid.prediction.temporal import TASKS, Event, Task, boundaries, candidates, history, horizon_labels

VERSION = "prediction-v2"
ORIGINS = (5, 6, 7, 8, 9)
FIRST_TRAIN = 2
NEG_RATE = 0.05
NEG_SEED = 11
MAX_ROWS = 2_000_000
TOTAL_LIMIT_S = 3600.0
REFERENCE = {"new_pair": "recent_activity_product_2H", "repeat_pair": "pair_recency"}
HEURISTICS = {
    "new_pair": ("random", "preferential_attachment", "resource_allocation", "recent_activity_product_2H",
                 "decay_activity_product", "recency_product", "temporal_triangle"),
    "repeat_pair": ("random", "preferential_attachment", "resource_allocation", "recent_activity_product_2H",
                    "pair_recency", "decay_activity_product", "recency_product", "temporal_triangle",
                    "decayed_pair_count"),
}
STRUCTURAL = ("common_neighbors", "jaccard", "adamic_adar", "resource_allocation", "preferential_attachment")
V1_TEMPORAL = ("recent_activity_product_H", "recent_activity_product_2H", "recent_resource_allocation_H")
COUNTS = {"common_neighbors", "preferential_attachment", "recent_activity_product_H", "recent_activity_product_2H",
          "decay_activity_product", "decay_activity_sum", "sent_sum", "received_sum", "pair_count",
          "pair_recency_s", "decayed_pair_count", "deg_sum", "act_H_sum"}


def feature_names(task: Task) -> tuple[str, ...]:
    base = STRUCTURAL + V1_TEMPORAL + V2_COLUMNS + ("deg_sum", "act_H_sum")
    return base + (("pair_count", "pair_recency_s") + V2_REPEAT if task == "repeat_pair" else ())


def design(columns: dict[str, np.ndarray], names: tuple[str, ...], rows: np.ndarray | slice = slice(None)) -> np.ndarray:
    out = []
    for name in names:
        col = columns["recency_s" if name == "pair_recency_s" else name][rows]
        out.append(np.log1p(np.maximum(col, 0)) if name in COUNTS else col)
    return np.column_stack(out).astype(np.float32)


def sample_mask(task: Task, cutoff: int, pairs: list, labels: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """All positives + seeded 5% of negatives (new_pair); weights undo the negative sampling."""
    if task == "repeat_pair":
        return np.ones(len(labels), bool), np.ones(len(labels))
    threshold = int(NEG_RATE * 2**64)
    keep = np.fromiter((int.from_bytes(hashlib.sha256(f"{NEG_SEED}|{cutoff}|{a}|{b}".encode()).digest()[:8], "big")
                        < threshold for a, b in pairs), dtype=bool, count=len(pairs))
    keep |= labels
    weights = np.where(labels, 1.0, 1.0 / NEG_RATE)
    return keep, weights


def fit_models(x: np.ndarray, y: np.ndarray, w: np.ndarray) -> dict:
    models = {}
    scaler = StandardScaler().fit(x, sample_weight=w)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        logit = LogisticRegression(C=1.0, max_iter=300).fit(scaler.transform(x), y, sample_weight=w)
    models["logistic_v2"] = {"converged": not any(issubclass(c.category, ConvergenceWarning) for c in caught),
                             "score": lambda z: logit.decision_function(scaler.transform(z))}
    hgb = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31, early_stopping=False,
                                         random_state=0).fit(x, y, sample_weight=w)
    models["hgb_v2"] = {"converged": True, "score": lambda z: hgb.decision_function(z)}
    return models


def run(events: list[Event], output: Path, *, protocol_path: Path | None = None, data_sha256: str = "synthetic",
        tasks: tuple[Task, ...] = TASKS, version: str = VERSION, primary: str = "hgb_v2",
        active_window_bins: int | None = None,
        note: str = "development evidence: every window was inspected under prediction-v1") -> Path:
    """`primary`/`active_window_bins` are fixed by each frozen protocol (v2: hgb_v2, no rule; v3: logistic_v2, 1 bin)."""
    started = time.perf_counter()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    b = boundaries(events)
    horizon = b[1] - b[0]
    tau = float(horizon)
    _save(output / "freeze.json", {"version": version, "data_sha256": data_sha256, "boundaries": b, "tau_s": tau,
                                   "primary": primary, "active_window_bins": active_window_bins,
                                   "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest()
                                   if protocol_path else None, "origins": ORIGINS,
                                   "started_utc": datetime.now(UTC).isoformat()})
    pool = {t: {"x": [], "y": [], "w": [], "cutoffs": []} for t in tasks}
    results = {t: {} for t in tasks}
    log = []
    for i in range(FIRST_TRAIN, ORIGINS[-1] + 1):
        if time.perf_counter() - started > TOTAL_LIMIT_S:
            raise TimeoutError("prediction-v2 wall-time budget exhausted")
        hist = history(events, b[i])
        if active_window_bins:
            hist.restrict_to_active(active_window_bins * horizon)  # candidate rule (history only)
        lab = horizon_labels(events, hist, b[i + 1])
        for task in tasks:
            t0 = time.perf_counter()
            snap = add_v2_columns(build_snapshot(hist, task, horizon), hist, task, tau)
            attach_labels(snap, hist, lab)
            names = feature_names(task)
            entry = {"cutoff_index": i, "task": task, "candidates": snap.size, "positives": int(snap.labels.sum())}
            if task == "new_pair":  # coverage: true new pairs among known nodes that the candidate rule excluded
                known_new = sum(1 for q in lab.positives if q not in hist.pair_count)
                entry["known_node_positives"] = known_new
                entry["excluded_by_candidate_rule"] = known_new - entry["positives"]
            if i in ORIGINS:  # score with models trained on strictly earlier cutoffs only
                p = pool[task]
                x, y, w = np.vstack(p["x"]), np.concatenate(p["y"]), np.concatenate(p["w"])
                entry["training_rows"], entry["training_cutoffs"] = int(len(y)), list(p["cutoffs"])
                if len(y) > MAX_ROWS:
                    raise RuntimeError(f"{task} training rows {len(y)} exceed the cap")
                models = fit_models(x, y, w)
                full = design(snap.columns, names)
                methods = {name: snap.columns[name] for name in HEURISTICS[task]}
                methods |= {name: m["score"](full) for name, m in models.items()}
                results[task][f"b{i}"] = {
                    "candidates": snap.size, "positives": int(snap.labels.sum()),
                    "prevalence": float(snap.labels.mean()) if snap.size else None,
                    "training_rows": int(len(y)), "training_cutoffs": list(p["cutoffs"]),
                    "logistic_converged": models["logistic_v2"]["converged"],
                    "excluded_by_candidate_rule": entry.get("excluded_by_candidate_rule"),
                    "known_node_positives": entry.get("known_node_positives"),
                    "methods": {name: rank_metrics_np(np.asarray(s, float), snap.tiebreak, snap.labels)
                                for name, s in methods.items()}}
            # only now does this cutoff join the training pool (its labels end at b_{i+1})
            pairs = list(candidates(hist, task))
            keep, weights = sample_mask(task, b[i], pairs, snap.labels)
            pool[task]["x"].append(design(snap.columns, names, keep))
            pool[task]["y"].append(snap.labels[keep])
            pool[task]["w"].append(weights[keep])
            pool[task]["cutoffs"].append(i)
            entry["elapsed_s"] = time.perf_counter() - t0
            log.append(entry)
            print(f"b{i} {task}: {entry['elapsed_s']:.1f}s", flush=True)
    summary = {}
    for task in tasks:
        windows = results[task]
        names = list(next(iter(windows.values()))["methods"])
        ref = REFERENCE[task]

        def mean(metric: str, m: str) -> float | None:
            vals = [w["methods"][m][metric] for w in windows.values() if w["methods"][m][metric] is not None]
            return float(np.mean(vals)) if vals else None

        def diff(w: dict) -> float | None:  # a non-evaluable origin (no positives) counts as not won
            a, r = w["methods"][primary]["average_precision"], w["methods"][ref]["average_precision"]
            return None if a is None or r is None else a - r
        diffs = {k: diff(w) for k, w in windows.items()}
        valid = [d for d in diffs.values() if d is not None]
        won = sum(d > 0 for d in valid)
        summary[task] = {"mean_ap": {m: mean("average_precision", m) for m in names},
                         "mean_p_at_100": {m: mean("precision_at_k", m) for m in names},
                         "primary": {"model": primary, "reference": ref, "ap_differences": diffs,
                                     "evaluable_origins": len(valid), "origins_won": won,
                                     "mean_difference": float(np.mean(valid)) if valid else None,
                                     "improved": bool(valid and np.mean(valid) > 0 and won >= 4)}}
    _save(output / "evaluation.json", {"version": version, "windows": results, "summary": summary, "log": log})
    _save(output / "suite.json", {"status": "completed", "elapsed_s": time.perf_counter() - started,
                                  "peak_memory_bytes": peak_memory_bytes(), "finished_utc": datetime.now(UTC).isoformat(),
                                  "note": note})
    return output
