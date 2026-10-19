"""Sprint 6 Session 6: prediction tools, predictive-claim checker and the forecast console path (offline)."""

from __future__ import annotations

import json

import pytest

from blackgrid.prediction import suite as suite_mod
from blackgrid.prediction.claims import check
from blackgrid.prediction.service import PredictionToolRejected, PredictionTools, forecast, parse
from blackgrid.prediction.synthetic import triadic_stream

SCOPE = {"task": "new_pair", "cutoff": 100, "horizon_s": 10, "candidate_policy": "complete known-node universe",
         "split": "prospective", "method": "resource_allocation"}
EV = {"f#/prediction/candidates": 1234, "f#/compare/cutoffs/b8/m/average_precision": 0.0123}


@pytest.fixture(scope="module")
def evaluated(tmp_path_factory):
    ev = triadic_stream(seed=9, nodes=60, events=3_000)
    out = suite_mod.run(ev, tmp_path_factory.mktemp("eval") / "sprint6")
    return ev, out


@pytest.mark.parametrize("request_,why", [
    ({"tool": "link_prediction", "args": {"task": "new_pair", "cutoff": 5}}, "cutoffs"),
    ({"tool": "link_prediction", "args": {"task": "new_pair", "method": "exec_python"}}, "code"),
    ({"tool": "prediction_compare", "args": {"task": "new_pair", "split": "test_labels"}}, "labels"),
    ({"tool": "shell", "args": {}}, "unknown"),
    ({"tool": "link_prediction", "args": {"task": "directed"}}, "invalid arguments"),
])
def test_planner_cannot_move_cutoffs_see_labels_or_run_code(request_, why):
    with pytest.raises(PredictionToolRejected, match=why):
        parse(request_)


def test_tools_return_aggregates_and_reject_unregistered_methods(evaluated):
    ev, out = evaluated
    tools = PredictionTools(ev, out)
    profile = tools.call({"tool": "temporal_profile", "args": {}})
    assert profile["history_nodes"] > 0 and isinstance(profile["candidates"]["new_pair"], int)
    result = tools.call({"tool": "link_prediction", "args": {"task": "new_pair", "method": "jaccard"}})
    # Aggregate history_pairs is allowed; identifiers and ranked rows must remain local.
    assert not {'pair','pairs','rows','local_ranking'} & result.keys()
    assert all(v is None or isinstance(v,(str,int,float,bool,dict)) for v in result.values())
    with pytest.raises(PredictionToolRejected, match="not registered"):
        tools.call({"tool": "link_prediction", "args": {"task": "new_pair", "method": "gnn"}})
    with pytest.raises(PredictionToolRejected, match="not registered"):
        tools.call({"tool": "link_prediction", "args": {"task": "new_pair", "method": "pair_recency"}})  # repeat-only


def test_test_aggregates_need_a_completed_frozen_evaluation(evaluated, tmp_path):
    ev, out = evaluated
    partial = tmp_path / "partial"
    partial.mkdir()
    for name in ("selection.json", "validation.json"):
        (partial / name).write_bytes((out / name).read_bytes())
    tools = PredictionTools(ev, partial)
    assert tools.call({"tool": "prediction_compare", "args": {"task": "new_pair"}})["split"] == "validation"
    with pytest.raises(PredictionToolRejected, match="frozen, completed evaluation"):
        tools.call({"tool": "prediction_compare", "args": {"task": "new_pair", "split": "test"}})


@pytest.mark.parametrize("text,rule", [
    ("There is an 80% chance these pairs will talk.", "P4"),
    ("Message activity causes new connections.", "P4"),
    ("This proves the ranking generalizes to all colleges.", "P4"),
    ("The forecast also predicts which new students will join.", "P5"),
    ("AP was 0.0123.", "P3"),
    ("1999 candidate pairs were ranked.", "P2"),
])
def test_predictive_claim_checker_rejects_overreach(text, rule):
    claim = {"text": text, "evidence": ["f#/prediction/candidates"], "scope": SCOPE}
    assert any(r.startswith(rule) for r in check(claim, EV, SCOPE))


def test_predictive_claim_checker_accepts_scoped_cited_claims_and_needs_scope():
    good = {"text": "1234 candidate pairs; average precision 0.0123 at b8.",
            "evidence": ["f#/prediction/candidates", "f#/compare/cutoffs/b8/m/average_precision"], "scope": SCOPE}
    assert check(good, EV, SCOPE) == []
    assert any(r.startswith("P1") for r in check(good | {"scope": {}}, EV, SCOPE))
    assert any(r.startswith("P1") for r in check(good | {"scope": SCOPE | {"split": "test"}}, EV, SCOPE))
    excluded = {"text": "New students first seen after the cutoff are excluded.", "evidence": ["f#/prediction/candidates"],
                "scope": SCOPE}
    assert check(excluded, EV, SCOPE) == []  # stating the exclusion is allowed


def test_forecast_writes_checked_claims_and_a_local_ranking(evaluated, tmp_path):
    ev, out = evaluated
    folder = forecast(ev, out, tmp_path / "runs" / "forecast-a", "new_pair")
    record = json.loads((folder / "forecast.json").read_text(encoding="utf-8"))
    assert record["usd"] == 0.0 and all(d["accepted"] for d in record["decisions"]), record["decisions"]
    assert "local_ranking.json" in record["local_ranking"] and (folder / "local_ranking.json").is_file()
    assert '"pair"' not in (folder / "forecast.json").read_text(encoding="utf-8")  # rankings stay in the local file
    from blackgrid.console.data import forecast_payload, index_payload
    from blackgrid.console.render import write_forecast_snapshot

    payload = forecast_payload(tmp_path / "runs", folder)
    assert payload["summary"]["kind"] == "forecast" and len(payload["ranking"]) <= 100
    assert any(r["kind"] == "forecast" for r in index_payload(tmp_path / "runs")["runs"])
    html = write_forecast_snapshot(tmp_path / "runs", folder).read_text(encoding="utf-8")
    assert "renderForecast" in html and "<script>alert" not in html


def test_rejected_forecast_leaves_no_folder(evaluated, tmp_path):
    ev, out = evaluated
    with pytest.raises(PredictionToolRejected):
        forecast(ev, out, tmp_path / "f", "new_pair", method="gnn")
    assert not (tmp_path / "f").exists()
