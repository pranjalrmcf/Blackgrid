"""Ranking metrics over the complete candidate universe (SPRINT_06.md §7).

Ordering: descending score, then ascending shared tie-break hash. AP is the mean, over positives,
of precision at each positive's rank (not trapezoidal PR-AUC). Precision@K and Recall@K use
K = min(100, candidates). ROC-AUC is supplementary and tie-aware (mid-ranks, ignoring the
tie-break). Zero positives or zero negatives make a metric `None` (not evaluable), never perfect.
"""
from __future__ import annotations

import time
from collections.abc import Iterable

from blackgrid.contracts import Contract
from blackgrid.prediction.scores import Method
from blackgrid.prediction.temporal import History, Labels, Pair, Task, batches, candidates, tiebreak

TOP_K = 100


class MethodResult(Contract):
    method: str
    family: str
    task: Task
    cutoff: int
    candidates: int
    positives: int
    prevalence: float | None
    average_precision: float | None
    precision_at_k: float | None
    recall_at_k: float | None
    k: int
    roc_auc: float | None
    tie_rate: float | None  # fraction of candidates sharing their score with another candidate
    elapsed_s: float
    status: str = "completed"  # completed | not_evaluable | timeout
    note: str | None = None


def rank_metrics(scored: list[tuple[float, int, bool]], k_max: int = TOP_K) -> dict:
    """`scored` = (score, tiebreak, is_positive). Returns AP, P@K, R@K, ROC-AUC, tie rate."""
    n = len(scored)
    pos = sum(1 for _, _, y in scored if y)
    k = min(k_max, n)
    out = {"candidates": n, "positives": pos, "prevalence": pos / n if n else None, "k": k,
           "average_precision": None, "precision_at_k": None, "recall_at_k": None, "roc_auc": None,
           "tie_rate": None}
    if n == 0:
        return out
    order = sorted(scored, key=lambda r: (-r[0], r[1]))
    hits = 0
    ap_sum = 0.0
    for rank, (_, _, y) in enumerate(order, 1):
        if y:
            hits += 1
            ap_sum += hits / rank
    top_hits = sum(1 for _, _, y in order[:k] if y)
    counts: dict[float, int] = {}
    for s, _, _ in scored:
        counts[s] = counts.get(s, 0) + 1
    out["tie_rate"] = sum(c for c in counts.values() if c > 1) / n
    if pos:
        out["average_precision"] = ap_sum / pos
        out["recall_at_k"] = top_hits / pos
        out["precision_at_k"] = top_hits / k if k else None
    neg = n - pos
    if pos and neg:  # Mann-Whitney U with mid-ranks over scores only
        ascending = sorted(scored, key=lambda r: r[0])
        rank_sum, i = 0.0, 0
        while i < n:
            j = i
            while j < n and ascending[j][0] == ascending[i][0]:
                j += 1
            mid = (i + 1 + j) / 2
            rank_sum += mid * sum(1 for r in ascending[i:j] if r[2])
            i = j
        out["roc_auc"] = (rank_sum - pos * (pos + 1) / 2) / (pos * neg)
    return out


def evaluate(method: Method, hist: History, lab: Labels, task: Task, horizon: int, *,
             time_limit_s: float = 120.0, pairs: Iterable[Pair] | None = None) -> MethodResult:
    """Score the full universe in batches, then compute metrics. The same candidates/ties for every method."""
    start = time.perf_counter()
    scorer = method.build(horizon)
    scored: list[tuple[float, int, bool]] = []
    for batch in batches(pairs if pairs is not None else candidates(hist, task)):
        for pair, score in zip(batch, scorer(hist, batch)):
            scored.append((score, tiebreak(pair), pair in lab.positives))
        if time.perf_counter() - start > time_limit_s:
            return MethodResult(method=method.name, family=method.family, task=task, cutoff=hist.cutoff,
                                candidates=len(scored), positives=0, prevalence=None, average_precision=None,
                                precision_at_k=None, recall_at_k=None, k=0, roc_auc=None, tie_rate=None,
                                elapsed_s=time.perf_counter() - start, status="timeout",
                                note=f"exceeded {time_limit_s} s; recorded, not extended")
    metrics = rank_metrics(scored)
    status = "completed" if metrics["average_precision"] is not None else "not_evaluable"
    return MethodResult(method=method.name, family=method.family, task=task, cutoff=hist.cutoff,
                        elapsed_s=time.perf_counter() - start, status=status,
                        note=None if status == "completed" else "no positives (or no candidates) at this cutoff",
                        **metrics)
