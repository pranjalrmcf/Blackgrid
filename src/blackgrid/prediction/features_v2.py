"""prediction-v2 features (protocols/sprint06_prediction_v2.md): decay, recency, temporal triangle, direction.

All values come from `History` (events strictly before the cutoff). The decay scale is tau = H.
"""
from __future__ import annotations

import math

import numpy as np

from blackgrid.prediction.features import Snapshot
from blackgrid.prediction.temporal import History, Pair, Task, batches, candidates, canonical

V2_COLUMNS = ("decay_activity_product", "decay_activity_sum", "recency_product", "temporal_triangle",
              "sent_sum", "received_sum")
V2_REPEAT = ("decayed_pair_count", "reciprocal")


def node_tables(hist: History, tau: float) -> tuple[dict[int, float], dict[int, float]]:
    """Decayed activity A(u) and last-event recency R(u) for every historical node."""
    decay, recency = {}, {}
    for node, times in hist.node_times.items():
        decay[node] = sum(math.exp(-(hist.cutoff - t) / tau) for t in times)
        recency[node] = math.exp(-(hist.cutoff - times[-1]) / tau) if times else 0.0
    return decay, recency


def pair_weights(hist: History, tau: float) -> dict[Pair, float]:
    """exp(-(t - last pair event)/tau) for every historical pair: the edge weights of the temporal triangle."""
    return {p: math.exp(-(hist.cutoff - last) / tau) for p, last in hist.pair_last.items()}


def temporal_triangle(hist: History, weights: dict[Pair, float], a: int, b: int) -> float:
    empty: frozenset[int] = frozenset()
    common = hist.adjacency.get(a, empty) & hist.adjacency.get(b, empty)
    return sum(weights[canonical(a, z)] * weights[canonical(b, z)] for z in common)


def add_v2_columns(snap: Snapshot, hist: History, task: Task, tau: float) -> Snapshot:
    """Append v2 columns in the same candidate order as `build_snapshot`."""
    n = snap.size
    names = V2_COLUMNS + (V2_REPEAT if task == "repeat_pair" else ())
    cols = {name: np.empty(n) for name in names}
    decay, recency = node_tables(hist, tau)
    weights = pair_weights(hist, tau)
    offset = 0
    for batch in batches(candidates(hist, task)):
        k = len(batch)
        da = np.array([decay.get(a, 0.0) for a, _ in batch])
        db = np.array([decay.get(b, 0.0) for _, b in batch])
        cols["decay_activity_product"][offset:offset + k] = da * db
        cols["decay_activity_sum"][offset:offset + k] = da + db
        cols["recency_product"][offset:offset + k] = [recency.get(a, 0.0) * recency.get(b, 0.0) for a, b in batch]
        cols["temporal_triangle"][offset:offset + k] = [temporal_triangle(hist, weights, a, b) for a, b in batch]
        cols["sent_sum"][offset:offset + k] = [hist.sent.get(a, 0) + hist.sent.get(b, 0) for a, b in batch]
        cols["received_sum"][offset:offset + k] = [hist.received.get(a, 0) + hist.received.get(b, 0) for a, b in batch]
        if task == "repeat_pair":
            cols["decayed_pair_count"][offset:offset + k] = [
                sum(math.exp(-(hist.cutoff - t) / tau) for t in hist.pair_times.get(p, ())) for p in batch]
            cols["reciprocal"][offset:offset + k] = [
                1.0 if (a, b) in hist.directed and (b, a) in hist.directed else 0.0 for a, b in batch]
        offset += k
    assert offset == n
    snap.columns.update(cols)
    return snap
