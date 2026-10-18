"""Cutoff-safe temporal pipeline: boundaries, history snapshots, labels and candidate universes.

Every quantity that a method may use is derived from `History`, which is built only from events
with timestamp < cutoff. Labels are a separate object built from `[cutoff, horizon_end)`. Nothing
here reads a future event to choose nodes, candidates or features (SPRINT_06.md §3-§5).
"""
from __future__ import annotations

import bisect
import hashlib
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Literal

from blackgrid.contracts import Contract

Event = tuple[int, int, int]  # (source, target, unix timestamp), as in blackgrid.collegemsg
Pair = tuple[int, int]  # canonical: (min, max)
Task = Literal["new_pair", "repeat_pair"]
TASKS: tuple[Task, ...] = ("new_pair", "repeat_pair")
BINS = 10
MAX_CANDIDATES = 2_000_000  # per task/cutoff (SPRINT_06.md §5)
BATCH = 50_000


class CapacityExceeded(RuntimeError):
    """A candidate universe is larger than the frozen cap; the protocol stops instead of sampling."""


def canonical(u: int, v: int) -> Pair:
    return (u, v) if u < v else (v, u)


def boundaries(events: Iterable[Event], bins: int = BINS) -> list[int]:
    """b_0..b_bins by elapsed time: t0 = min ts, t_end = max ts + 1, b_i = t0 + floor(i * D / bins)."""
    times = [t for _, _, t in events]
    if not times:
        raise ValueError("no events")
    t0, t_end = min(times), max(times) + 1
    span = t_end - t0
    if span < bins:
        raise ValueError(f"time span {span} s is too short for {bins} bins")
    return [t0 + (i * span) // bins for i in range(bins)] + [t_end]


@dataclass
class History:
    """Everything observable strictly before `cutoff`."""

    cutoff: int
    nodes: frozenset[int]
    adjacency: dict[int, frozenset[int]]
    pair_count: Counter  # canonical pair -> historical event count (repeats preserved)
    pair_last: dict[Pair, int]  # canonical pair -> last historical timestamp
    node_times: dict[int, list[int]]  # node -> sorted timestamps of incident historical events
    pair_times: dict[Pair, list[int]] = field(repr=False, default_factory=dict)
    events: int = 0
    self_loops_excluded: int = 0

    def degree(self, node: int) -> int:
        return len(self.adjacency.get(node, ()))

    def activity(self, node: int, window: int) -> int:
        """Historical events incident on `node` within [cutoff - window, cutoff)."""
        times = self.node_times.get(node, [])
        return len(times) - bisect.bisect_left(times, self.cutoff - window)

    def recent_adjacency(self, window: int) -> dict[int, set[int]]:
        """Simple graph of pairs with at least one event within [cutoff - window, cutoff)."""
        start = self.cutoff - window
        recent: dict[int, set[int]] = defaultdict(set)
        for (a, b), times in self.pair_times.items():
            if times and times[-1] >= start:
                recent[a].add(b)
                recent[b].add(a)
        return recent

    def fingerprint(self) -> str:
        """Hash of the historical pair multiset and node set: changes iff the observable past changes."""
        h = hashlib.sha256()
        for node in sorted(self.nodes):
            h.update(f"n{node};".encode())
        for pair in sorted(self.pair_count):
            h.update(f"p{pair[0]},{pair[1]},{self.pair_count[pair]},{self.pair_last[pair]};".encode())
        return h.hexdigest()


def history(events: Iterable[Event], cutoff: int) -> History:
    adjacency: dict[int, set[int]] = defaultdict(set)
    pair_count: Counter = Counter()
    pair_last: dict[Pair, int] = {}
    node_times: dict[int, list[int]] = defaultdict(list)
    pair_times: dict[Pair, list[int]] = defaultdict(list)
    nodes: set[int] = set()
    used = loops = 0
    for u, v, t in events:
        if t >= cutoff:
            continue  # the future: never read here
        used += 1
        nodes.update((u, v))
        if u == v:
            loops += 1
            node_times[u].append(t)
            continue
        pair = canonical(u, v)
        adjacency[u].add(v)
        adjacency[v].add(u)
        pair_count[pair] += 1
        pair_last[pair] = max(pair_last.get(pair, t), t)
        node_times[u].append(t)
        node_times[v].append(t)
        pair_times[pair].append(t)
    for times in (*node_times.values(), *pair_times.values()):
        times.sort()
    return History(cutoff=cutoff, nodes=frozenset(nodes), adjacency={k: frozenset(s) for k, s in adjacency.items()},
                   pair_count=pair_count, pair_last=pair_last, node_times=dict(node_times),
                   pair_times=dict(pair_times), events=used, self_loops_excluded=loops)


@dataclass(frozen=True)
class Labels:
    """Observed interactions in [cutoff, end). Absence means *no observed interaction*, not no relationship."""

    cutoff: int
    end: int
    positives: frozenset[Pair]  # among known-node pairs only
    cold_start_pairs: int  # future pairs with at least one endpoint unseen before the cutoff (excluded)
    self_loops: int


def horizon_labels(events: Iterable[Event], hist: History, end: int) -> Labels:
    known, cold, loops = set(), set(), 0
    for u, v, t in events:
        if not hist.cutoff <= t < end:
            continue
        if u == v:
            loops += 1
            continue
        pair = canonical(u, v)
        (known if u in hist.nodes and v in hist.nodes else cold).add(pair)
    return Labels(cutoff=hist.cutoff, end=end, positives=frozenset(known), cold_start_pairs=len(cold),
                  self_loops=loops)


def candidate_count(hist: History, task: Task) -> int:
    n = len(hist.nodes)
    return n * (n - 1) // 2 - len(hist.pair_count) if task == "new_pair" else len(hist.pair_count)


def candidates(hist: History, task: Task) -> Iterator[Pair]:
    """The complete eligible universe in a deterministic order (streamed; no dense matrix)."""
    count = candidate_count(hist, task)
    if count > MAX_CANDIDATES:
        raise CapacityExceeded(f"{task} at cutoff {hist.cutoff}: {count} candidates > cap {MAX_CANDIDATES}")
    if task == "repeat_pair":
        yield from sorted(hist.pair_count)
        return
    ordered = sorted(hist.nodes)
    for i, a in enumerate(ordered):
        neighbours = hist.adjacency.get(a, frozenset())
        for b in ordered[i + 1:]:
            if b not in neighbours:
                yield (a, b)


def batches(pairs: Iterable[Pair], size: int = BATCH) -> Iterator[list[Pair]]:
    batch: list[Pair] = []
    for pair in pairs:
        batch.append(pair)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def tiebreak(pair: Pair, seed: int = 0) -> int:
    """Seeded, label-independent hash shared by every method (SPRINT_06.md §5)."""
    return int.from_bytes(hashlib.sha256(f"{seed}|{pair[0]}|{pair[1]}".encode()).digest()[:8], "big")


class SnapshotManifest(Contract):
    """Aggregate, shareable description of one task/cutoff (no pair or node identifiers)."""

    version: str
    task: Task
    cutoff: int
    horizon_end: int
    history_events: int
    history_nodes: int
    history_pairs: int
    history_fingerprint: str
    candidates: int
    candidate_sha256: str
    positives: int
    prevalence: float | None
    cold_start_positive_pairs_excluded: int
    self_loops_excluded_history: int
    self_loops_in_horizon: int


def snapshot_manifest(hist: History, lab: Labels, task: Task) -> SnapshotManifest:
    from blackgrid.prediction import PREDICTION_VERSION

    h = hashlib.sha256()
    positives = 0
    count = 0
    for pair in candidates(hist, task):
        count += 1
        h.update(f"{pair[0]},{pair[1]};".encode())
        positives += pair in lab.positives
    return SnapshotManifest(version=PREDICTION_VERSION, task=task, cutoff=hist.cutoff, horizon_end=lab.end,
                            history_events=hist.events, history_nodes=len(hist.nodes),
                            history_pairs=len(hist.pair_count), history_fingerprint=hist.fingerprint(),
                            candidates=count, candidate_sha256=h.hexdigest(), positives=positives,
                            prevalence=positives / count if count else None,
                            cold_start_positive_pairs_excluded=lab.cold_start_pairs,
                            self_loops_excluded_history=hist.self_loops_excluded, self_loops_in_horizon=lab.self_loops)
