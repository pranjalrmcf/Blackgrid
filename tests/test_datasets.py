"""Generic dataset loader and the prediction-v3 candidate rule (offline fixtures; no raw Bitcoin rows)."""

from __future__ import annotations

import hashlib

import pytest

import blackgrid.data.datasets as D
from blackgrid.prediction.temporal import candidate_count, candidates, history


def register(tmp_path, monkeypatch, text: str, **kw):
    path = tmp_path / "f.csv"
    path.write_text(text, encoding="utf-8")
    schema = D.DatasetSchema(dataset_id="fixture", path="f.csv", sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                             rights_decision="test", rights_status="accepted_local_noncommercial", citations=("x",),
                             source_url="local", semantics="test edge", **kw)
    monkeypatch.setitem(D.REGISTRY, "fixture", schema)
    return schema


def test_csv_with_attributes_and_float_times(tmp_path, monkeypatch):
    register(tmp_path, monkeypatch, "7,9,4,100.9\n9,7,-2,200.1\nbad,row\n7,7,1,300\n", separator=",", time_col=3,
             attribute_cols={"rating": 2})
    data = D.load("fixture", tmp_path)
    assert data.events == [(0, 1, 100), (1, 0, 200), (0, 0, 300)]  # dense IDs in first-seen order
    assert data.attributes["rating"] == [4.0, -2.0, 1.0]
    assert data.profile["malformed_by_reason"] == {"too_few_fields": 1} and data.profile["self_loop_events"] == 1


def test_tsv_header_text_ids_and_datetimes(tmp_path, monkeypatch):
    register(tmp_path, monkeypatch, "SRC\tDST\tPOST\tTIME\nalpha\tbeta\tp1\t2014-01-01 00:00:10\n", separator="\t",
             header=True, time_col=3, time_format="datetime")
    data = D.load("fixture", tmp_path)
    assert data.events == [(0, 1, 1388534410)] and data.profile["nodes"] == 2


def test_unregistered_and_tampered_datasets_are_refused(tmp_path, monkeypatch):
    with pytest.raises(D.DatasetError, match="not registered"):
        D.load("snap-reddit-hyperlinks", tmp_path)  # no rights decision recorded
    schema = register(tmp_path, monkeypatch, "1 2 3\n")
    (tmp_path / schema.path).write_text("1 2 4\n", encoding="utf-8")
    with pytest.raises(D.DatasetError, match="checksum mismatch"):
        D.load("fixture", tmp_path)


def test_active_candidate_rule_uses_history_only():
    ev = [(0, 1, 10), (2, 3, 90), (3, 4, 95), (5, 6, 99)]
    hist = history(ev, 100).restrict_to_active(20)  # active in [80, 100): nodes 2..6
    pairs = set(candidates(hist, "new_pair"))
    assert all(a >= 2 and b >= 2 for a, b in pairs) and (2, 3) not in pairs  # old pairs are not new
    assert candidate_count(hist, "new_pair") == len(pairs) == 10 - 3
    assert set(candidates(hist, "repeat_pair")) == {(0, 1), (2, 3), (3, 4), (5, 6)}  # repeat task is unrestricted
