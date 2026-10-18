"""prediction-v2: hand-checked new features, no leakage, earlier-only training, sampled reweighting."""

from __future__ import annotations

import json
import math

import numpy as np

from blackgrid.prediction import rolling
from blackgrid.prediction.features import build_snapshot
from blackgrid.prediction.features_v2 import add_v2_columns, node_tables, pair_weights, temporal_triangle
from blackgrid.prediction.synthetic import triadic_stream
from blackgrid.prediction.temporal import boundaries, candidates, history, horizon_labels

TAU = 100.0


def test_decay_recency_and_triangle_by_hand():
    # cutoff 200: 0-1 at 100 and 150, 1-2 at 190, 0-2 never; 3 sent to 0 at 180
    ev = [(0, 1, 100), (1, 0, 150), (1, 2, 190), (3, 0, 180)]
    hist = history(ev, 200)
    decay, recency = node_tables(hist, TAU)
    assert math.isclose(decay[0], math.exp(-1) + math.exp(-0.5) + math.exp(-0.2))
    assert math.isclose(recency[2], math.exp(-0.1))
    w = pair_weights(hist, TAU)
    # (0, 2): common neighbour 1, w(0,1) = exp(-0.5), w(1,2) = exp(-0.1)
    assert math.isclose(temporal_triangle(hist, w, 0, 2), math.exp(-0.5) * math.exp(-0.1))
    assert hist.sent[1] == 2 and hist.received[0] == 2 and (1, 0) in hist.directed and (0, 1) in hist.directed


def test_repeat_features_reciprocity_and_decayed_count():
    ev = [(0, 1, 100), (1, 0, 150), (1, 2, 190)]
    hist = history(ev, 200)
    snap = add_v2_columns(build_snapshot(hist, "repeat_pair", 100), hist, "repeat_pair", TAU)
    order = list(candidates(hist, "repeat_pair"))
    i01, i12 = order.index((0, 1)), order.index((1, 2))
    assert snap.columns["reciprocal"][i01] == 1.0 and snap.columns["reciprocal"][i12] == 0.0
    assert math.isclose(snap.columns["decayed_pair_count"][i01], math.exp(-1) + math.exp(-0.5))


def test_v2_features_do_not_see_the_future():
    base = triadic_stream(seed=4, nodes=40, events=1_500)
    cut = boundaries(base)[6]
    mutated = [e for e in base if e[2] < cut] + [(e[1], e[0], e[2] + 1) for e in base if e[2] >= cut]
    for task in ("new_pair", "repeat_pair"):
        cols = []
        for ev in (base, mutated):
            hist = history(ev, cut)
            cols.append(add_v2_columns(build_snapshot(hist, task, 1000), hist, task, 1000.0).columns)
        for name in cols[0]:
            assert np.array_equal(cols[0][name], cols[1][name]), name


def test_negative_sampling_keeps_positives_and_reweights():
    pairs = [(i, i + 1) for i in range(20_000)]
    labels = np.zeros(len(pairs), bool)
    labels[:50] = True
    keep, w = rolling.sample_mask("new_pair", 123, pairs, labels)
    assert keep[:50].all() and abs(keep[50:].mean() - rolling.NEG_RATE) < 0.01
    assert (w[labels] == 1).all() and (w[~labels] == 1 / rolling.NEG_RATE).all()
    assert np.array_equal(keep, rolling.sample_mask("new_pair", 123, pairs, labels)[0])  # seeded


def test_rolling_trains_only_on_earlier_cutoffs(tmp_path):
    ev = triadic_stream(seed=9, nodes=70, events=3_500)
    out = rolling.run(ev, tmp_path / "v2")
    data = json.loads((out / "evaluation.json").read_text(encoding="utf-8"))
    for task, windows in data["windows"].items():
        for key, w in windows.items():
            origin = int(key[1:])
            assert w["training_cutoffs"] and max(w["training_cutoffs"]) < origin  # never this or a later cutoff
            assert {"hgb_v2", "logistic_v2", rolling.REFERENCE[task]} <= set(w["methods"])
    s = data["summary"]["new_pair"]["primary"]
    assert set(s["ap_differences"]) == {f"b{i}" for i in rolling.ORIGINS} and isinstance(s["improved"], bool)
