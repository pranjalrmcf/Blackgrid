"""Registered scoring methods (SPRINT_06.md §6, stages 0-2). One frozen configuration each.

Every method maps (History, batch of canonical pairs) to scores using history only. Conventions:
Adamic-Adar uses the natural logarithm; a common neighbour always has degree >= 2, so log(k) > 0.
Empty denominators score 0. Higher score = ranked earlier; ties are broken by the shared
`temporal.tiebreak` hash, never by labels.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from blackgrid.prediction.temporal import History, Pair, Task, tiebreak

Scorer = Callable[[History, list[Pair]], list[float]]


def _common(hist: History, a: int, b: int) -> frozenset[int]:
    empty: frozenset[int] = frozenset()
    return hist.adjacency.get(a, empty) & hist.adjacency.get(b, empty)


def common_neighbors(hist: History, pairs: list[Pair]) -> list[float]:
    return [float(len(_common(hist, a, b))) for a, b in pairs]


def jaccard(hist: History, pairs: list[Pair]) -> list[float]:
    out = []
    empty: frozenset[int] = frozenset()
    for a, b in pairs:
        na, nb = hist.adjacency.get(a, empty), hist.adjacency.get(b, empty)
        union = len(na | nb)
        out.append(len(na & nb) / union if union else 0.0)
    return out


def adamic_adar(hist: History, pairs: list[Pair]) -> list[float]:
    return [sum(1.0 / math.log(hist.degree(z)) for z in _common(hist, a, b)) for a, b in pairs]


def resource_allocation(hist: History, pairs: list[Pair]) -> list[float]:
    return [sum(1.0 / hist.degree(z) for z in _common(hist, a, b)) for a, b in pairs]


def preferential_attachment(hist: History, pairs: list[Pair]) -> list[float]:
    return [float(hist.degree(a) * hist.degree(b)) for a, b in pairs]


def random_control(hist: History, pairs: list[Pair], seed: int = 7) -> list[float]:
    """Seeded random ranking: a hash independent of labels and of the shared tie-break seed."""
    return [tiebreak(p, seed=seed) / 2**64 for p in pairs]


def constant_control(hist: History, pairs: list[Pair]) -> list[float]:
    return [0.0] * len(pairs)


def recent_activity_product(window: int) -> Scorer:
    def score(hist: History, pairs: list[Pair]) -> list[float]:
        return [float(hist.activity(a, window) * hist.activity(b, window)) for a, b in pairs]
    return score


def recent_resource_allocation(window: int) -> Scorer:
    def score(hist: History, pairs: list[Pair]) -> list[float]:
        recent = hist.recent_adjacency(window)
        out = []
        for a, b in pairs:
            common = recent.get(a, set()) & recent.get(b, set())
            out.append(sum(1.0 / len(recent[z]) for z in common))
        return out
    return score


def pair_frequency(hist: History, pairs: list[Pair]) -> list[float]:
    return [float(hist.pair_count.get(p, 0)) for p in pairs]


def pair_recency(hist: History, pairs: list[Pair]) -> list[float]:
    """Fixed monotone score: minus seconds since the last historical pair event (more recent = higher)."""
    return [-(hist.cutoff - hist.pair_last[p]) for p in pairs]


@dataclass(frozen=True)
class Method:
    name: str
    family: str  # control | structural | temporal
    tasks: tuple[Task, ...]
    build: Callable[[int], Scorer]  # horizon (seconds) -> scorer


BOTH: tuple[Task, ...] = ("new_pair", "repeat_pair")
METHODS: tuple[Method, ...] = (
    Method("random", "control", BOTH, lambda h: random_control),
    Method("constant", "control", BOTH, lambda h: constant_control),
    Method("common_neighbors", "structural", BOTH, lambda h: common_neighbors),
    Method("jaccard", "structural", BOTH, lambda h: jaccard),
    Method("adamic_adar", "structural", BOTH, lambda h: adamic_adar),
    Method("resource_allocation", "structural", BOTH, lambda h: resource_allocation),
    Method("preferential_attachment", "structural", BOTH, lambda h: preferential_attachment),
    Method("recent_activity_product_H", "temporal", BOTH, lambda h: recent_activity_product(h)),
    Method("recent_activity_product_2H", "temporal", BOTH, lambda h: recent_activity_product(2 * h)),
    Method("recent_resource_allocation_H", "temporal", BOTH, lambda h: recent_resource_allocation(h)),
    Method("recent_resource_allocation_2H", "temporal", BOTH, lambda h: recent_resource_allocation(2 * h)),
    Method("pair_frequency", "temporal", ("repeat_pair",), lambda h: pair_frequency),
    Method("pair_recency", "temporal", ("repeat_pair",), lambda h: pair_recency),
)
REGISTRY = {m.name: m for m in METHODS}


def methods_for(task: Task) -> list[Method]:
    return [m for m in METHODS if task in m.tasks]
