"""Session 5: trusted, deterministic evaluation of prediction-v1 (protocols/sprint06_prediction_v1.md).

Order is enforced in code: validation and selection -> selection frozen to disk -> test forecasts
scored and saved -> only then are test labels read and metrics computed. No agent or LLM is
involved; this is trusted orchestration. Pair-level artifacts stay under the local output folder.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from blackgrid.prediction import PREDICTION_VERSION
from blackgrid.prediction import scores as S
from blackgrid.prediction.fast import rank_metrics_np
from blackgrid.prediction.features import Snapshot, attach_labels, build_snapshot, two_hop_mask
from blackgrid.prediction.model import GRID, MAX_TRAINING_ROWS, TrainingCapacityExceeded, fit
from blackgrid.prediction.temporal import TASKS, Event, Task, boundaries, candidate_count, history, horizon_labels, \
    snapshot_manifest

DEV, VAL, TEST = (2, 3, 4, 5), (6, 7), (8, 9)
METHOD_LIMIT_S = 120.0
TOTAL_LIMIT_S = 3600.0
MAX_FITS = 30


def peak_memory_bytes() -> int | None:
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]
            c = Counters()
            c.cb = ctypes.sizeof(c)
            psapi = ctypes.WinDLL("psapi")
            kernel32 = ctypes.WinDLL("kernel32")
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            # Without argtypes the 64-bit pseudo-handle is truncated and the call fails (sprint6-v1 recorded None).
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
            if psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb):
                return int(c.PeakWorkingSetSize)
            return None
        import resource

        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * (1 if sys.platform == "darwin" else 1024)
    except Exception:
        return None


def _save(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, indent=2, sort_keys=True, default=str) + "\n").encode("utf-8")
    with path.open("xb") as fh:  # never overwrite a scientific output
        fh.write(data)
    return hashlib.sha256(data).hexdigest()


def _metrics(scores: np.ndarray, snap: Snapshot, mask: np.ndarray | None = None) -> dict:
    if mask is None:
        return rank_metrics_np(scores, snap.tiebreak, snap.labels)
    return rank_metrics_np(scores[mask], snap.tiebreak[mask], snap.labels[mask])


def run(events: list[Event], output: Path, *, protocol_path: Path | None = None, data_sha256: str = "synthetic",
        tasks: tuple[Task, ...] = TASKS) -> Path:
    started = time.perf_counter()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    b = boundaries(events)
    horizon = b[1] - b[0]
    protocol_sha = hashlib.sha256(protocol_path.read_bytes()).hexdigest() if protocol_path else None
    attempts: list[dict] = []
    fits = 0

    def budget() -> None:
        if time.perf_counter() - started > TOTAL_LIMIT_S:
            raise TimeoutError("prediction-v1 total wall-time budget exhausted")

    _save(output / "freeze.json", {"version": PREDICTION_VERSION, "protocol_sha256": protocol_sha,
                                   "data_sha256": data_sha256, "boundaries": b, "horizon_s": horizon,
                                   "roles": {"development": DEV, "validation": VAL, "test": TEST},
                                   "started_utc": datetime.now(UTC).isoformat(), "python": sys.version.split()[0],
                                   "platform": platform.platform(), "numpy": np.__version__})
    validation: dict = {}
    selection: dict = {}
    fitted_final: dict = {}
    for task in tasks:
        budget()
        methods = S.methods_for(task)
        val_rows: dict[str, list] = {m.name: [] for m in methods}
        val_snaps = []
        dev_rows = sum(candidate_count(history(events, b[i]), task) for i in DEV)  # history-only size check
        trainable = dev_rows <= MAX_TRAINING_ROWS
        for i in VAL:
            hist = history(events, b[i])
            lab = horizon_labels(events, hist, b[i + 1])
            snap = attach_labels(build_snapshot(hist, task, horizon, extra=trainable), hist, lab)
            manifest = snapshot_manifest(hist, lab, task).model_dump()
            if trainable:
                val_snaps.append(snap)  # kept only when the logistic model will need them
            for m in methods:
                status = "timeout" if snap.elapsed_s[m.name] > METHOD_LIMIT_S else "completed"
                res = _metrics(snap.columns[m.name], snap) | {"cutoff_index": i, "status": status,
                                                              "scoring_s": snap.elapsed_s[m.name]}
                val_rows[m.name].append(res)
            attempts.append({"phase": "validation", "task": task, "cutoff_index": i, "manifest": manifest})
        # Session 4: logistic model on development snapshots (capacity checked from history before building)
        logistic: dict = {}
        if not trainable:
            logistic["status"] = "capacity_exceeded"
            logistic["note"] = f"{dev_rows} supervised development rows > 2,000,000 cap; not sampled (protocol §3)"
        else:
            dev = []
            for i in DEV:
                hist = history(events, b[i])
                dev.append(attach_labels(build_snapshot(hist, task, horizon), hist,
                                         horizon_labels(events, hist, b[i + 1])))
            logistic["configs"] = {}
            for c in GRID:
                budget()
                fits += 1
                try:
                    model = fit(task, dev, c)
                except (ValueError, TrainingCapacityExceeded) as exc:
                    logistic["configs"][str(c)] = {"status": "failed", "error": str(exc)}
                    continue
                if not model.converged:
                    logistic["configs"][str(c)] = {"status": "failed", "error": "nonconvergence within 200 iterations"}
                    continue
                rows = [_metrics(model.score(s), s) | {"cutoff_index": i} for s, i in zip(val_snaps, VAL)]
                logistic["configs"][str(c)] = {"status": "completed", "iterations": model.iterations, "validation": rows}
            logistic["development_rows"] = dev_rows
        # selection on mean validation AP; ties -> registry order (simplest first), then smaller C
        table = {}
        for m in methods:
            rows = val_rows[m.name]
            evaluable = all(r["average_precision"] is not None and r["status"] == "completed" for r in rows)
            table[m.name] = {"family": m.family, "rows": rows,
                             "mean_ap": float(np.mean([r["average_precision"] for r in rows])) if evaluable else None}
        for c, cfg in (logistic.get("configs") or {}).items():
            if cfg["status"] == "completed":
                aps = [r["average_precision"] for r in cfg["validation"]]
                table[f"logistic_C{c}"] = {"family": "temporal", "rows": cfg["validation"],
                                           "mean_ap": float(np.mean(aps)) if None not in aps else None}

        def best(family: str) -> str | None:
            names = [n for n, row in table.items() if row["family"] == family and row["mean_ap"] is not None]
            return max(names, key=lambda n: (table[n]["mean_ap"], -list(table).index(n))) if names else None
        choice = {"static_reference": best("structural"), "temporal": best("temporal")}
        validation[task] = {"table": table, "logistic": logistic}
        selection[task] = choice
        if choice["temporal"] and choice["temporal"].startswith("logistic_C"):
            c = float(choice["temporal"].removeprefix("logistic_C"))
            refit = []
            for i in DEV + VAL:  # labels of these snapshots all end by b8
                hist = history(events, b[i])
                refit.append(attach_labels(build_snapshot(hist, task, horizon), hist,
                                           horizon_labels(events, hist, b[i + 1])))
            fits += 1
            model = fit(task, refit, c)
            fitted_final[task] = model
            selection[task]["refit"] = {"rows": sum(s.size for s in refit), "converged": model.converged,
                                        "coefficients": dict(zip(model.names, map(float, model.model.coef_[0])))}
        if fits > MAX_FITS:
            raise RuntimeError("fitted-configuration budget exceeded")
    _save(output / "validation.json", validation)
    selection_sha = _save(output / "selection.json", {"selection": selection, "frozen_utc": datetime.now(UTC).isoformat(),
                                                      "note": "frozen before any test forecast or test label"})
    # --- test forecasts: score and save BEFORE reading any test label -----------------------------------------
    predictions: dict = {}
    for task in tasks:
        for i in TEST:
            budget()
            hist = history(events, b[i])
            snap = build_snapshot(hist, task, horizon, extra=task in fitted_final)
            cols = {m.name: snap.columns[m.name] for m in S.methods_for(task)}
            if task in fitted_final:
                cols[selection[task]["temporal"]] = fitted_final[task].score(snap)
            folder = output / "local_predictions" / f"{task}_b{i}"
            folder.mkdir(parents=True)
            hashes = {}
            for name, arr in cols.items():
                path = folder / f"{name}.npy"
                np.save(path, arr)
                hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            np.save(folder / "tiebreak.npy", snap.tiebreak)
            np.save(folder / "common_neighbors_mask.npy", two_hop_mask(snap))
            predictions[f"{task}_b{i}"] = {"hashes": hashes, "candidates": snap.size}
    predictions_sha = _save(output / "predictions_manifest.json", {"selection_sha256": selection_sha,
                                                                   "predictions": predictions})
    # --- trusted evaluator: labels are read only now ---------------------------------------------------------
    test: dict = {}
    for task in tasks:
        test[task] = {"cutoffs": {}}
        for i in TEST:
            hist = history(events, b[i])
            lab = horizon_labels(events, hist, b[i + 1])
            folder = output / "local_predictions" / f"{task}_b{i}"
            entry = predictions[f"{task}_b{i}"]
            snap = Snapshot(task=task, cutoff=b[i], horizon=horizon, columns={}, labels=None,
                            tiebreak=np.load(folder / "tiebreak.npy"))
            attach_labels(snap, hist, lab)
            mask = np.load(folder / "common_neighbors_mask.npy")
            rows = {}
            for name, digest in entry["hashes"].items():
                path = folder / f"{name}.npy"
                if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                    raise ValueError(f"frozen prediction changed: {path.name}")
                scores_ = np.load(path)
                rows[name] = _metrics(scores_, snap)
                if task == "new_pair" and name in selection[task].values():
                    rows[name]["two_hop"] = _metrics(scores_, snap, mask)
                    rows[name]["no_two_hop"] = _metrics(scores_, snap, ~mask)
            test[task]["cutoffs"][f"b{i}"] = {"manifest": snapshot_manifest(hist, lab, task).model_dump(), "methods": rows}
        chosen = selection[task]
        if chosen["static_reference"] and chosen["temporal"]:
            diffs = []
            for key, cut in test[task]["cutoffs"].items():
                t_ap = cut["methods"][chosen["temporal"]]["average_precision"]
                s_ap = cut["methods"][chosen["static_reference"]]["average_precision"]
                diffs.append(None if None in (t_ap, s_ap) else t_ap - s_ap)
            test[task]["paired_ap_difference_temporal_minus_static"] = diffs
            test[task]["mean_ap_difference"] = float(np.mean(diffs)) if None not in diffs else None
    _save(output / "test_evaluation.json", {"predictions_manifest_sha256": predictions_sha, "test": test})
    _save(output / "suite.json", {"status": "completed", "elapsed_s": time.perf_counter() - started,
                                  "fitted_configurations": fits, "peak_memory_bytes": peak_memory_bytes(),
                                  "finished_utc": datetime.now(UTC).isoformat(), "attempts": attempts})
    return output
