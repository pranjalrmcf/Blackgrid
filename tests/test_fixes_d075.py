"""D-075: crash status, upstream parameter routing, and console fixes."""

from __future__ import annotations

import io
import json

import pytest

import blackgrid.workflow.engine as engine
from blackgrid.agent import providers
from blackgrid.agent.providers import OpenRouterProvider

from tests.test_workflow import Counting, only_run, start


def test_unexpected_error_leaves_a_resumable_pause_not_running(tmp_path, monkeypatch):
    from blackgrid.workflow.runner import resume_investigation
    from blackgrid.workflow.api import open_services

    real = engine.finalize_run
    calls = {"n": 0}

    def broken_once(rt, state):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("simulated bug in finalize")
        return real(rt, state)
    monkeypatch.setattr(engine, "finalize_run", broken_once)
    with pytest.raises(ValueError):
        start(tmp_path, Counting(), None)
    run_id = only_run(tmp_path)
    services = open_services(tmp_path)
    try:
        row = services.store.run(run_id)
        assert row["status"] == "paused" and row["lock_owner"] is None
        assert json.loads(row["pause_json"])["kind"] == "internal_error" and "simulated bug" in row["status_reason"]
    finally:
        services.close()
    shown = json.loads((tmp_path / run_id / "workflow_status.json").read_text(encoding="utf-8"))
    assert shown["status"] == "paused"  # the console stops treating it as running
    done = resume_investigation(run_id, tmp_path, provider=Counting(), cache_dir=None)
    assert done.outcome.status == "completed"  # after the fix, resume finishes from the checkpoint


def test_openrouter_requires_parameter_support_and_records_the_upstream(capture_openrouter_http):
    sent = {}

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request, timeout):
        sent.update(json.loads(request.data.decode("utf-8")))
        return Response(json.dumps({"provider": "SomeUpstream", "model": "m",
                                    "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                                    "usage": {"prompt_tokens": 1, "completion_tokens": 1}}).encode())
    capture_openrouter_http(fake_urlopen)
    done = OpenRouterProvider("m", "sk-test", reasoning_max_tokens=12_000).complete("planner", {}, [], 16_000)
    assert sent['provider'].pop('max_price')==pytest.approx({'prompt':.2,'completion':.6})
    assert sent["provider"] == {"require_parameters": True, "sort":"latency"} and sent["reasoning"] == {"max_tokens": 12_000}
    assert done.provider == "openrouter:SomeUpstream"


def test_console_keeps_drafts_and_trims_forecast_tabs():
    from blackgrid.console.render import template

    html = template()
    assert "const draft = {question: null" in html and "draft.question ??" in html
    assert 'sum.family === "forecast" ? allTabs.filter' in html


def test_validation_ap_claims_are_checkable(tmp_path):
    """A true validation-AP comparison cites paths that name the metric, so the forecast checker accepts it."""
    from blackgrid.prediction import suite as suite_mod
    from blackgrid.prediction.claims import check
    from blackgrid.prediction.service import PredictionCompareArgs, PredictionTools
    from blackgrid.prediction.synthetic import triadic_stream
    from blackgrid.workflow.engine import flatten

    ev = triadic_stream(seed=9, nodes=50, events=2_000)
    out = suite_mod.run(ev, tmp_path / "eval")
    val = PredictionTools(ev, out).prediction_compare(PredictionCompareArgs(task="repeat_pair"))
    evidence = flatten({"prediction_compare.json": val})
    m = "pair_recency"
    v = val["methods"][m]["mean_average_precision"]
    scope = {"task": "repeat_pair", "cutoff": 1, "horizon_s": 1, "candidate_policy": "x", "split": "validation",
             "method": m}
    claim = {"text": f"On validation, {m} mean AP is {v:.3f}.", "scope": scope,
             "evidence": [f"prediction_compare.json#/methods/{m}/mean_average_precision"]}
    assert check(claim, evidence, scope) == []
