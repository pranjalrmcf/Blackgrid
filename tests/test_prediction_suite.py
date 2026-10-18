"""Sprint 6 Sessions 4-5 on synthetic data: logistic baseline, vectorized metrics, sealed-test ordering."""

from __future__ import annotations

import json
import random

import numpy as np
import pytest

from blackgrid.prediction import suite as suite_mod
from blackgrid.prediction.fast import rank_metrics_np
from blackgrid.prediction.metrics import rank_metrics
from blackgrid.prediction.model import TrainingCapacityExceeded, feature_names, fit
from blackgrid.prediction.features import attach_labels, build_snapshot
from blackgrid.prediction.synthetic import triadic_stream
from blackgrid.prediction.temporal import boundaries, history, horizon_labels


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_vectorized_metrics_equal_the_reference(seed):
    rng = random.Random(seed)
    rows = [(float(rng.randint(0, 5)), rng.getrandbits(32), rng.random() < 0.2) for _ in range(500)]
    ref = rank_metrics(rows)
    s, tb, y = (np.array([r[i] for r in rows]) for i in range(3))
    fast = rank_metrics_np(s, tb.astype(np.uint64), y.astype(bool))
    for key, value in ref.items():
        assert (fast[key] is None and value is None) or abs(fast[key] - value) < 1e-12, key


def _dev(ev, task):
    b = boundaries(ev)
    out = []
    for i in (2, 3, 4, 5):
        hist = history(ev, b[i])
        out.append(attach_labels(build_snapshot(hist, task, b[1] - b[0]), hist, horizon_labels(ev, hist, b[i + 1])))
    return out


def test_logistic_baseline_fits_with_training_only_scaling():
    ev = triadic_stream(seed=5, nodes=60, events=3_000)
    model = fit("repeat_pair", _dev(ev, "repeat_pair"), 1.0)
    assert model.converged and model.names == feature_names("repeat_pair")
    assert "pair_count" in model.names and all("node" not in n for n in model.names)  # no identity features


def test_training_capacity_is_a_recorded_stop(monkeypatch):
    import blackgrid.prediction.model as M

    monkeypatch.setattr(M, "MAX_TRAINING_ROWS", 10)
    with pytest.raises(TrainingCapacityExceeded):
        M.fit("new_pair", _dev(triadic_stream(seed=5, nodes=40, events=1_500), "new_pair"), 1.0)


def test_suite_freezes_selection_and_predictions_before_reading_test_labels(tmp_path, monkeypatch):
    ev = triadic_stream(seed=9, nodes=70, events=3_500)
    b = boundaries(ev)
    order: list[str] = []
    real = suite_mod.horizon_labels

    def spy(events, hist, end):
        if hist.cutoff in (b[8], b[9]):
            order.append("test_labels:" + str((tmp_path / "out" / "predictions_manifest.json").exists()))
        return real(events, hist, end)
    monkeypatch.setattr(suite_mod, "horizon_labels", spy)
    out = suite_mod.run(ev, tmp_path / "out")
    assert order and all(o == "test_labels:True" for o in order)  # every test-label read came after the freeze
    sel = json.loads((out / "selection.json").read_text(encoding="utf-8"))["selection"]
    assert set(sel) == {"new_pair", "repeat_pair"} and all(v["static_reference"] for v in sel.values())
    test = json.loads((out / "test_evaluation.json").read_text(encoding="utf-8"))["test"]
    assert set(test["new_pair"]["cutoffs"]) == {"b8", "b9"}
    chosen = sel["new_pair"]["static_reference"]
    assert "two_hop" in test["new_pair"]["cutoffs"]["b8"]["methods"][chosen]
    assert json.loads((out / "suite.json").read_text(encoding="utf-8"))["status"] == "completed"


def test_tampered_frozen_prediction_is_rejected(tmp_path, monkeypatch):
    """A prediction file altered after the freeze (and before evaluation) stops the evaluator."""
    ev = triadic_stream(seed=9, nodes=50, events=2_000)
    real_save = suite_mod._save

    def save_then_tamper(path, value):
        digest = real_save(path, value)
        if path.name == "predictions_manifest.json":
            folder = next((path.parent / "local_predictions").iterdir())
            victim = folder / "resource_allocation.npy"
            np.save(victim, np.load(victim) + 1.0)
        return digest
    monkeypatch.setattr(suite_mod, "_save", save_then_tamper)
    with pytest.raises(ValueError, match="frozen prediction changed"):
        suite_mod.run(ev, tmp_path / "out")


def test_peak_memory_is_measured():
    value = suite_mod.peak_memory_bytes()
    assert value is not None and value > 1_000_000  # a real reading, not a silent None
