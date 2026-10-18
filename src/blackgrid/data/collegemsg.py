"""CollegeMsg loader, size-only window selection, and undirected projection (protocol §3, §5).

The raw file is opened read-only and never modified. Repeated events are preserved; exact
duplicate rows are flagged, not removed. Only aggregate counts leave this module in manifests.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import networkx as nx

from blackgrid.contracts import (
    DataOrigin,
    DatasetSource,
    EdgeStatus,
    GraphRecord,
    WindowRule,
)

Event = tuple[int, int, int]  # (source_id, target_id, unix_timestamp)


class DataIntegrityError(RuntimeError):
    """The input file is missing or does not match its recorded checksum."""


@dataclass(frozen=True)
class EventTable:
    """Valid directed events in file order, plus validation counts for the manifest."""

    events: tuple[Event, ...]
    sha256: str
    total_lines: int
    blank_or_comment_lines: int
    malformed: dict[str, int]
    malformed_line_numbers: tuple[int, ...]  # first few only, for debugging; not identifiers
    timestamp_decreases: int

    @property
    def malformed_rows(self) -> int:
        return sum(self.malformed.values())

    def summary(self) -> dict:
        events = self.events
        return {
            "sha256": self.sha256,
            "total_lines": self.total_lines,
            "blank_or_comment_lines": self.blank_or_comment_lines,
            "valid_events": len(events),
            "malformed_rows": self.malformed_rows,
            "malformed_by_reason": dict(sorted(self.malformed.items())),
            "malformed_line_numbers_sample": list(self.malformed_line_numbers),
            "timestamp_decreases_in_file_order": self.timestamp_decreases,
            **event_counts(events),
        }


def event_counts(events: tuple[Event, ...] | list[Event]) -> dict:
    """Aggregate counts used for both the full table and the selected window."""
    rows = Counter(events)
    pairs = Counter((s, t) for s, t, _ in events)
    undirected = {(min(s, t), max(s, t)) for s, t, _ in events if s != t}
    nodes = {n for s, t, _ in events for n in (s, t)}
    with_edges = {n for pair in undirected for n in pair}
    timestamps = [ts for _, _, ts in events]
    return {
        "events": len(events),
        "self_loop_events": sum(1 for s, t, _ in events if s == t),
        "exact_duplicate_rows": sum(c - 1 for c in rows.values() if c > 1),
        "repeated_directed_pair_events": sum(c - 1 for c in pairs.values() if c > 1),
        "distinct_directed_pairs": len(pairs),
        "unique_undirected_pairs": len(undirected),
        "active_nodes": len(nodes),
        "self_loop_only_nodes": len(nodes - with_edges),
        "min_timestamp": min(timestamps) if timestamps else None,
        "max_timestamp": max(timestamps) if timestamps else None,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_events(path: Path, expected_sha256: str, *, sample_limit: int = 10) -> EventTable:
    """Verify the checksum, then parse `source target timestamp` rows.

    Malformed rows are excluded and counted by reason; they never abort the load silently or
    get repaired. Callers decide whether the counts make the data unusable.
    """
    if not path.is_file():
        raise DataIntegrityError(f"input file not found: {path}")
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise DataIntegrityError(f"checksum mismatch: expected {expected_sha256}, got {actual}")

    events: list[Event] = []
    malformed: Counter[str] = Counter()
    bad_lines: list[int] = []
    skipped = decreases = 0
    previous_ts: int | None = None
    line_no = 0

    with path.open("rb") as fh:
        for line_no, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line or line.startswith(b"#"):
                skipped += 1
                continue
            reason, event = _parse(line)
            if reason:
                malformed[reason] += 1
                if len(bad_lines) < sample_limit:
                    bad_lines.append(line_no)
                continue
            if previous_ts is not None and event[2] < previous_ts:
                decreases += 1
            previous_ts = event[2]
            events.append(event)

    return EventTable(
        events=tuple(events),
        sha256=actual,
        total_lines=line_no,
        blank_or_comment_lines=skipped,
        malformed=dict(malformed),
        malformed_line_numbers=tuple(bad_lines),
        timestamp_decreases=decreases,
    )


def _parse(line: bytes) -> tuple[str | None, Event | None]:
    parts = line.split()
    if len(parts) != 3:
        return "wrong_field_count", None
    try:
        source, target, ts = (int(p) for p in parts)
    except ValueError:
        return "non_integer", None
    if source < 0 or target < 0 or ts < 0:
        return "negative_value", None
    return None, (source, target, ts)


# --- Window selection ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CandidateSize:
    index: int
    duration_s: int
    start_ts: int
    end_ts: int  # exclusive
    active_nodes: int
    unique_edges: int
    within_caps: bool


@dataclass(frozen=True)
class WindowSelection:
    """Outcome of the frozen size-only rule. `chosen` is None when the rule abstains."""

    candidates: tuple[CandidateSize, ...]
    chosen: CandidateSize | None
    abstention_reason: str | None = None
    events: tuple[Event, ...] = field(default=(), repr=False)

    def summary(self) -> dict:
        return {
            "rule": "earliest half-open [t0, t0+d), first d within both caps",
            "candidates": [c.__dict__ for c in self.candidates],
            "chosen_index": None if self.chosen is None else self.chosen.index,
            "abstention_reason": self.abstention_reason,
        }


def select_window(events: tuple[Event, ...], rule: WindowRule) -> WindowSelection:
    """Try candidate durations in protocol order; choose the first within both size caps.

    Selection reads only node and pair counts, never any community or experiment output.
    """
    if not events:
        return WindowSelection(candidates=(), chosen=None, abstention_reason="no valid events")
    t0 = min(ts for _, _, ts in events)
    tried: list[CandidateSize] = []
    for index, duration in enumerate(rule.candidate_seconds):
        end = t0 + duration
        window = tuple(e for e in events if t0 <= e[2] < end)
        counts = event_counts(window)
        size = CandidateSize(
            index=index,
            duration_s=duration,
            start_ts=t0,
            end_ts=end,
            active_nodes=counts["active_nodes"],
            unique_edges=counts["unique_undirected_pairs"],
            within_caps=counts["active_nodes"] <= rule.max_active_nodes
            and counts["unique_undirected_pairs"] <= rule.max_unique_edges,
        )
        tried.append(size)
        if size.within_caps:
            return WindowSelection(candidates=tuple(tried), chosen=size, events=window)
    return WindowSelection(
        candidates=tuple(tried),
        chosen=None,
        abstention_reason="no candidate window satisfies the node and edge caps",
    )


# --- Projection ---------------------------------------------------------------------------------


def project(events: tuple[Event, ...]) -> nx.Graph:
    """Simple undirected unweighted graph over all active nodes; self-loops excluded.

    Nodes whose only events are self-loops remain as isolated nodes so the node set equals the
    active set; their count is reported separately.
    """
    graph = nx.Graph()
    for source, target, _ in events:
        graph.add_node(source)
        graph.add_node(target)
        if source != target:
            graph.add_edge(source, target)
    return graph


def graph_sha256(graph: nx.Graph) -> str:
    """Order-independent hash of a simple undirected graph's node and edge sets."""
    nodes = sorted(graph.nodes())
    edges = sorted((min(u, v), max(u, v)) for u, v in graph.edges())
    payload = json.dumps({"nodes": nodes, "edges": edges}, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class BoundedGraph:
    record: GraphRecord
    graph: nx.Graph
    table: EventTable
    selection: WindowSelection | None  # None for the full-dataset scope (no window is selected)

    def scope_summary(self) -> dict:
        """What part of the data the graph covers (window_selection.json or full_scope.json)."""
        if self.selection is not None:
            return self.selection.summary()
        r = self.record
        return {"scope": "full_dataset", "rule": "every valid event; no window", "start_ts": r.window_start_ts,
                "end_ts_exclusive": r.window_end_ts, "events": r.window_events, "active_nodes": r.active_nodes,
                "unique_edges": r.unique_edges}

    @property
    def scope_artifact(self) -> str:
        return "window_selection.json" if self.selection is not None else "full_scope.json"


def build_full_graph(root: Path, source: DatasetSource, *, graph_id: str = "collegemsg-full") -> BoundedGraph:
    """exp-v2-full: project every valid event (same loader and projection as the window path)."""
    table = load_events(root / source.path, source.sha256)
    if not table.events:
        raise DataIntegrityError("no valid events to analyse")
    counts = event_counts(table.events)
    graph = project(table.events)
    record = GraphRecord(
        graph_id=graph_id,
        origin=DataOrigin.REAL_PUBLIC,
        source=source,
        scope="full_dataset",
        window_start_ts=counts["min_timestamp"],
        window_end_ts=counts["max_timestamp"] + 1,
        window_candidate_index=None,
        raw_events=len(table.events),
        window_events=len(table.events),
        self_loop_events_excluded=counts["self_loop_events"],
        exact_duplicate_rows_flagged=counts["exact_duplicate_rows"],
        active_nodes=graph.number_of_nodes(),
        unique_edges=graph.number_of_edges(),
        edge_status_counts={EdgeStatus.OBSERVED: graph.number_of_edges()},
        projection_sha256=graph_sha256(graph),
    )
    return BoundedGraph(record=record, graph=graph, table=table, selection=None)


def build_graph(root: Path, config) -> BoundedGraph | WindowSelection:
    """The graph a run config asks for: the frozen first window (default) or the full dataset."""
    if getattr(config, "scope", "first_window") == "full_dataset":
        return build_full_graph(root, config.dataset)
    return build_bounded_graph(root, config.dataset, config.window)


def build_bounded_graph(
    root: Path, source: DatasetSource, rule: WindowRule, *, graph_id: str = "collegemsg-window"
) -> BoundedGraph | WindowSelection:
    """Load, select the window, and project. Returns the selection itself when the rule abstains."""
    table = load_events(root / source.path, source.sha256)
    selection = select_window(table.events, rule)
    if selection.chosen is None:
        return selection
    window_counts = event_counts(selection.events)
    graph = project(selection.events)
    record = GraphRecord(
        graph_id=graph_id,
        origin=DataOrigin.REAL_PUBLIC,
        source=source,
        window_start_ts=selection.chosen.start_ts,
        window_end_ts=selection.chosen.end_ts,
        window_candidate_index=selection.chosen.index,
        raw_events=len(table.events),
        window_events=len(selection.events),
        self_loop_events_excluded=window_counts["self_loop_events"],
        exact_duplicate_rows_flagged=window_counts["exact_duplicate_rows"],
        active_nodes=graph.number_of_nodes(),
        unique_edges=graph.number_of_edges(),
        edge_status_counts={EdgeStatus.OBSERVED: graph.number_of_edges()},
        projection_sha256=graph_sha256(graph),
    )
    return BoundedGraph(record=record, graph=graph, table=table, selection=selection)
