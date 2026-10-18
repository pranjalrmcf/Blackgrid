"""Loader and window rule checked against hand-derived answers in tests/fixtures/collegemsg."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from blackgrid.data.collegemsg import event_counts, load_events, select_window
from blackgrid.contracts import WindowRule

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "collegemsg"
EXPECTED = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_fixture(name):
    want = EXPECTED[name]
    path = FIXTURES / name
    assert hashlib.sha256(path.read_bytes()).hexdigest() == want["sha256"], "fixture bytes changed"

    table = load_events(path, want["sha256"])
    summary = table.summary()
    for key in ("valid_events", "malformed_rows", "exact_duplicate_rows", "self_loop_events"):
        assert summary[key] == want[key], key
    assert table.timestamp_decreases == want["timestamp_decreases"]

    selection = select_window(table.events, WindowRule())
    if want["chosen_index"] is None:
        assert selection.chosen is None and selection.abstention_reason
        return
    assert selection.chosen.index == want["chosen_index"]
    window = event_counts(selection.events)
    assert window["events"] == want["window_events"]
    assert window["active_nodes"] == want["window_active_nodes"]
    assert window["unique_undirected_pairs"] == want["window_unique_edges"]


def test_every_fixture_file_has_an_expectation():
    files = {p.name for p in FIXTURES.glob("*.txt")}
    assert files == set(EXPECTED)
