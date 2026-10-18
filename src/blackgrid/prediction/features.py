"""Per-cutoff feature matrices: every registered method's score as one column (history only).

Columns are produced by the registered scorers in `scores.py`, batch by batch, so heuristic
rankings and logistic features are the same numbers. No identity features. Memory is about
8 bytes x columns x candidates (1.75M x 18 -> about 250 MB for the largest CollegeMsg cutoff).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from blackgrid.prediction import scores as S
from blackgrid.prediction.temporal import History, Labels, Pair, Task, batches, candidate_count, candidates, tiebreak

# Extra (non-ranking) columns used only by the logistic model.
EXTRA = ("deg_sum", "deg_product", "act_H_sum", "act_H_product", "pair_count", "recency_s", "recency_unseen")


@dataclass
class Snapshot:
    task: Task
    cutoff: int
    horizon: int
    columns: dict[str, np.ndarray]  # method/feature name -> float64 scores, candidate order
    tiebreak: np.ndarray  # uint64, shared by all methods
    labels: np.ndarray | None  # bool; None until a trusted caller attaches them
    elapsed_s: dict[str, float] = field(default_factory=dict)  # per-column scoring time

    @property
    def size(self) -> int:
        return len(self.tiebreak)


def build_snapshot(hist: History, task: Task, horizon: int, *, extra: bool = True,
                   pair_filter: list[Pair] | None = None) -> Snapshot:
    """Score the complete universe for `task` at `hist.cutoff` with every applicable method."""
    methods = S.methods_for(task)
    n = len(pair_filter) if pair_filter is not None else candidate_count(hist, task)
    cols = {m.name: np.empty(n) for m in methods}
    extras = {name: np.empty(n) for name in EXTRA} if extra else {}
    tb = np.empty(n, dtype=np.uint64)
    timing = {m.name: 0.0 for m in methods}
    scorers = {m.name: m.build(horizon) for m in methods}
    offset = 0
    source = pair_filter if pair_filter is not None else candidates(hist, task)
    for batch in batches(source):
        k = len(batch)
        for name, scorer in scorers.items():
            start = time.perf_counter()
            cols[name][offset:offset + k] = scorer(hist, batch)
            timing[name] += time.perf_counter() - start
        tb[offset:offset + k] = [tiebreak(p) for p in batch]
        if extra:
            da = np.array([hist.degree(a) for a, _ in batch], float)
            db = np.array([hist.degree(b) for _, b in batch], float)
            aa = np.array([hist.activity(a, horizon) for a, _ in batch], float)
            ab = np.array([hist.activity(b, horizon) for _, b in batch], float)
            extras["deg_sum"][offset:offset + k] = da + db
            extras["deg_product"][offset:offset + k] = da * db
            extras["act_H_sum"][offset:offset + k] = aa + ab
            extras["act_H_product"][offset:offset + k] = aa * ab
            extras["pair_count"][offset:offset + k] = [hist.pair_count.get(p, 0) for p in batch]
            last = [hist.pair_last.get(p) for p in batch]
            extras["recency_s"][offset:offset + k] = [hist.cutoff - t if t is not None else 0.0 for t in last]
            extras["recency_unseen"][offset:offset + k] = [1.0 if t is None else 0.0 for t in last]
        offset += k
    assert offset == n
    return Snapshot(task=task, cutoff=hist.cutoff, horizon=horizon, columns=cols | extras, tiebreak=tb, labels=None,
                    elapsed_s=timing)


def attach_labels(snap: Snapshot, hist: History, lab: Labels, pairs: list[Pair] | None = None) -> Snapshot:
    """Trusted step: label each candidate (same order as build_snapshot)."""
    source = pairs if pairs is not None else candidates(hist, snap.task)
    snap.labels = np.fromiter((p in lab.positives for p in source), dtype=bool, count=snap.size)
    return snap


def two_hop_mask(snap: Snapshot) -> np.ndarray:
    """Candidates with a historical two-hop path (common neighbours > 0): the new-pair diagnostic split."""
    return snap.columns["common_neighbors"] > 0
