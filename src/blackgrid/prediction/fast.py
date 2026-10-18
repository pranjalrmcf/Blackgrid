"""Vectorized ranking metrics, identical in definition to `metrics.rank_metrics` (checked by tests)."""
from __future__ import annotations

import numpy as np

from blackgrid.prediction.metrics import TOP_K


def rank_metrics_np(scores: np.ndarray, tb: np.ndarray, labels: np.ndarray, k_max: int = TOP_K) -> dict:
    n = int(len(scores))
    pos = int(labels.sum())
    k = min(k_max, n)
    out = {"candidates": n, "positives": pos, "prevalence": pos / n if n else None, "k": k,
           "average_precision": None, "precision_at_k": None, "recall_at_k": None, "roc_auc": None, "tie_rate": None}
    if n == 0:
        return out
    order = np.lexsort((tb, -scores))  # primary: descending score; then ascending tie-break hash
    ranked = labels[order]
    _, inverse, counts = np.unique(scores, return_inverse=True, return_counts=True)
    out["tie_rate"] = float(counts[inverse][counts[inverse] > 1].size / n)
    if pos:
        hits = np.cumsum(ranked)
        ranks = np.arange(1, n + 1)
        out["average_precision"] = float((hits[ranked] / ranks[ranked]).sum() / pos)
        top = int(ranked[:k].sum())
        out["recall_at_k"] = top / pos
        out["precision_at_k"] = top / k if k else None
    neg = n - pos
    if pos and neg:  # mid-rank Mann-Whitney, ties on score only
        uniq, inv = np.unique(scores, return_inverse=True)
        count = np.bincount(inv)
        upper = np.cumsum(count)
        mid = upper - (count - 1) / 2.0
        rank_sum = float(mid[inv][labels].sum())
        out["roc_auc"] = (rank_sum - pos * (pos + 1) / 2) / (pos * neg)
    return out
