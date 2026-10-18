"""Loader, window, and projection checks on hand-computable event files."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from blackgrid.data.collegemsg import (
    BoundedGraph,
    DataIntegrityError,
    WindowSelection,
    build_bounded_graph,
    graph_sha256,
    load_events,
    project,
    select_window,
)
from blackgrid.contracts import DatasetSource, RightsStatus, WindowRule

DAY = 86_400
REAL = Path(__file__).resolve().parents[1] / "data" / "CollegeMsg.txt" / "CollegeMsg.txt"
REAL_SHA = "e00ba2415373dee52c00616065bcceaa4750e78de60d1855c76470600f10740f"


def write(tmp_path: Path, text: str, name: str = "events.txt") -> tuple[Path, str]:
    path = tmp_path / name
    path.write_bytes(text.encode("utf-8"))
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def source_for(path: Path, sha: str, root: Path) -> DatasetSource:
    return DatasetSource(
        dataset_id="fixture",
        path=path.relative_to(root).as_posix(),
        sha256=sha,
        source_url="local-fixture",
        citations=("fixture",),
        rights_status=RightsStatus.ACCEPTED_LOCAL_NONCOMMERCIAL,
        rights_decision="D-003",
    )


# --- loader -------------------------------------------------------------------------------------

MESSY = """\
1 2 100
1 2 100
2 1 150
3 3 160

# comment
1 2
a b 170
4 5 -1
4 5 120
"""


def test_loader_counts_schema_problems_and_preserves_repeats(tmp_path):
    path, sha = write(tmp_path, MESSY)
    table = load_events(path, sha)
    assert table.events == ((1, 2, 100), (1, 2, 100), (2, 1, 150), (3, 3, 160), (4, 5, 120))
    assert table.malformed == {"wrong_field_count": 1, "non_integer": 1, "negative_value": 1}
    assert table.malformed_line_numbers == (7, 8, 9)
    assert table.blank_or_comment_lines == 2
    assert table.timestamp_decreases == 1  # 160 -> 120
    s = table.summary()
    assert s["exact_duplicate_rows"] == 1  # second "1 2 100" flagged, not removed
    assert s["repeated_directed_pair_events"] == 1
    assert s["self_loop_events"] == 1
    assert s["unique_undirected_pairs"] == 2  # {1,2}, {4,5}
    assert s["active_nodes"] == 5
    assert s["self_loop_only_nodes"] == 1  # node 3


def test_checksum_mismatch_and_missing_file_fail(tmp_path):
    path, _ = write(tmp_path, "1 2 3\n")
    with pytest.raises(DataIntegrityError, match="checksum"):
        load_events(path, "0" * 64)
    with pytest.raises(DataIntegrityError, match="not found"):
        load_events(tmp_path / "absent.txt", "0" * 64)


def test_loader_never_modifies_raw_file(tmp_path):
    path, sha = write(tmp_path, MESSY)
    load_events(path, sha)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha


# --- window -------------------------------------------------------------------------------------


def test_window_is_half_open_and_anchored_at_min_timestamp():
    events = ((5, 6, 1_000 + 7 * DAY), (1, 2, 1_000), (2, 3, 1_000 + 7 * DAY - 1))
    selection = select_window(events, WindowRule())
    assert selection.chosen.index == 0
    assert (selection.chosen.start_ts, selection.chosen.end_ts) == (1_000, 1_000 + 7 * DAY)
    assert set(selection.events) == {(1, 2, 1_000), (2, 3, 1_000 + 7 * DAY - 1)}  # end excluded


def star_events(n_leaves: int, ts: int, hub: int = 0) -> list[tuple[int, int, int]]:
    return [(hub, hub + 1 + i, ts) for i in range(n_leaves)]


def test_window_falls_back_in_protocol_order_on_size_only():
    t0 = 10_000
    early = star_events(500, t0)                      # inside 6h
    day2 = star_events(600, t0 + 2 * DAY, hub=5_000)  # inside 3d and 7d, outside 1d
    selection = select_window(tuple(early + day2), WindowRule())
    assert [c.index for c in selection.candidates] == [0, 1, 2]
    assert [c.within_caps for c in selection.candidates] == [False, False, True]
    assert selection.chosen.duration_s == DAY
    assert selection.chosen.active_nodes == 501


def test_window_abstains_when_no_candidate_fits():
    selection = select_window(tuple(star_events(1_000, 0)), WindowRule())  # 1,001 nodes in one second
    assert selection.chosen is None
    assert len(selection.candidates) == 4
    assert "caps" in selection.abstention_reason
    assert select_window((), WindowRule()).abstention_reason == "no valid events"


def test_edge_cap_alone_can_reject_a_window():
    nodes = range(150)  # 150 nodes, 11,175 pairs > 10,000
    clique = tuple((u, v, 0) for u in nodes for v in nodes if u < v)
    selection = select_window(clique, WindowRule())
    assert selection.chosen is None
    assert all(c.active_nodes <= 1_000 and c.unique_edges > 10_000 for c in selection.candidates)


# --- projection ---------------------------------------------------------------------------------


def test_projection_aggregates_repeats_and_reciprocals_and_drops_self_loops():
    graph = project(((1, 2, 0), (2, 1, 1), (1, 2, 2), (3, 3, 3), (2, 4, 4)))
    assert sorted(graph.edges()) == [(1, 2), (2, 4)]
    assert sorted(graph.nodes()) == [1, 2, 3, 4]  # self-loop-only node kept as isolate
    assert not graph.is_directed() and not any(u == v for u, v in graph.edges())


def test_graph_hash_ignores_input_order_and_detects_changes():
    a = project(((1, 2, 0), (3, 4, 1)))
    b = project(((4, 3, 9), (2, 1, 5)))
    assert graph_sha256(a) == graph_sha256(b)
    assert graph_sha256(a) != graph_sha256(project(((1, 2, 0), (3, 5, 1))))


def test_build_bounded_graph_records_counts(tmp_path):
    path, sha = write(tmp_path, MESSY)
    built = build_bounded_graph(tmp_path, source_for(path, sha, tmp_path), WindowRule())
    assert isinstance(built, BoundedGraph)
    r = built.record
    assert (r.raw_events, r.window_events, r.self_loop_events_excluded, r.exact_duplicate_rows_flagged) == (5, 5, 1, 1)
    assert (r.active_nodes, r.unique_edges) == (5, 2)


def test_build_bounded_graph_returns_abstention(tmp_path):
    text = "".join(f"0 {i} 0\n" for i in range(1, 1_001))
    path, sha = write(tmp_path, text)
    built = build_bounded_graph(tmp_path, source_for(path, sha, tmp_path), WindowRule())
    assert isinstance(built, WindowSelection) and built.chosen is None


# --- real file (local only; the raw data is not distributed) ------------------------------------


@pytest.mark.skipif(not REAL.is_file(), reason="CollegeMsg raw file not present locally")
def test_real_file_matches_published_counts():
    table = load_events(REAL, REAL_SHA)
    s = table.summary()
    assert (s["valid_events"], s["malformed_rows"], s["active_nodes"]) == (59_835, 0, 1_899)
    assert s["unique_undirected_pairs"] <= 20_296  # SNAP static edges are directed pairs
