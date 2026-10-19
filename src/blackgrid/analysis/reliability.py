"""Typed sampling eligibility, paired graph bootstrap and probability diagnostics."""
from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score

CLIP = 1e-12


def interval_eligibility(unit: str, count: int, *, independent: bool = False) -> dict:
    ok = unit == "graph" and independent and count >= 30
    return {"eligible": ok, "unit": unit, "count": count,
            "reason": "independent graph-level paired resampling" if ok else
            "insufficient justified independent units; no confidence interval"}


def paired_bootstrap(differences, *, seed: int = 74000, independent: bool = False) -> dict:
    x = np.asarray(differences, float)
    gate = interval_eligibility("graph", len(x), independent=independent)
    if x.ndim != 1 or not np.isfinite(x).all() or not gate["eligible"]:
        raise ValueError("bootstrap requires at least 30 finite independent graph summaries")
    samples = np.random.default_rng(seed).choice(x, size=(1000, len(x))).mean(axis=1)
    return {"mean_difference": float(x.mean()), "interval": np.quantile(samples, [0.025, 0.975]).tolist(),
            "interval_type": "95% paired graph bootstrap confidence interval", "resamples": 1000,
            "seed": seed, "scope": "conditional on the registered graph generator"}


def diagnostics(probabilities, labels) -> dict:
    p, y = np.asarray(probabilities, float), np.asarray(labels)
    if p.ndim != 1 or p.shape != y.shape or not len(p) or not np.isfinite(p).all():
        raise ValueError("nonempty matching finite probability/label arrays required")
    if np.any((p < 0) | (p > 1)) or not np.isin(y, [0, 1]).all():
        raise ValueError("probabilities must be in [0,1] and labels binary")
    y = y.astype(float)
    q = np.clip(p, CLIP, 1 - CLIP)
    bins = []
    indexes = np.minimum((p * 10).astype(int), 9)
    for i in range(10):
        mask = indexes == i
        n = int(mask.sum())
        bins.append({"lower": i / 10, "upper": (i + 1) / 10, "count": n,
                     "mean_probability": float(p[mask].mean()) if n else None,
                     "observed_fraction": float(y[mask].mean()) if n else None, "sparse": n < 30})
    prevalence = float(y.mean())
    return {"brier": float(np.mean((p - y) ** 2)),
            "log_loss": float(-np.mean(y * np.log(q) + (1 - y) * np.log1p(-q))),
            "prevalence": prevalence, "prevalence_brier": prevalence * (1 - prevalence),
            "average_precision": float(average_precision_score(y, p)) if y.sum() else None,
            "roc_auc": float(roc_auc_score(y, p)) if 0 < y.sum() < len(y) else None,
            "bins": bins, "clip": CLIP, "probability_display": False,
            "limitation": "proper scores combine calibration and discrimination; no display criterion registered",
            "degenerate_labels": len(np.unique(y)) < 2}


@dataclass(frozen=True)
class CalibrationPartition:
    role: str
    start: int
    end: int
    scores: np.ndarray
    labels: np.ndarray


def validate_partitions(parts: list[CalibrationPartition]) -> None:
    if [p.role for p in parts] != ["train", "selection", "fit", "assessment", "test"]:
        raise ValueError("train -> selection -> fit -> assessment -> test required")
    for p in parts:
        if p.start >= p.end or p.scores.ndim != 1 or p.scores.shape != p.labels.shape:
            raise ValueError("invalid partition")
    if any(a.end > b.start for a, b in zip(parts, parts[1:])):
        raise ValueError("overlapping chronological partitions")


def fit_sigmoid(part: CalibrationPartition):
    """Only the calibration-fit partition is accepted; assessment/test never enter fitting."""
    if part.role != "fit" or len(np.unique(part.labels)) != 2:
        raise ValueError("nondegenerate calibration-fit partition required")
    if not np.isfinite(part.scores).all() or not np.isin(part.labels, [0, 1]).all():
        raise ValueError("invalid calibration values")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        model = LogisticRegression(C=1e6, max_iter=300).fit(part.scores[:, None], part.labels)
    if any(issubclass(w.category, ConvergenceWarning) for w in caught):
        raise ValueError("sigmoid fit did not converge")
    return model


def disagreement(scores: dict[str, np.ndarray], ties: np.ndarray, k: int = 100) -> dict:
    if len(scores) < 2 or k < 1 or not len(ties):
        raise ValueError("two compatible nonempty rankings required")
    sets = {}
    for name, values in scores.items():
        x = np.asarray(values)
        if x.shape != ties.shape or not np.isfinite(x).all():
            raise ValueError("incompatible ranking candidates")
        sets[name] = set(np.lexsort((ties, -x))[:k].tolist())
    names = list(sets)
    return {"top_set_jaccard": {f"{a}/{b}": len(sets[a] & sets[b]) / len(sets[a] | sets[b])
                               for i, a in enumerate(names) for b in names[i + 1:]},
            "tie_policy": "shared label-independent tiebreak", "k": k,
            "interpretation": "ranking disagreement diagnostic, not epistemic variance"}
