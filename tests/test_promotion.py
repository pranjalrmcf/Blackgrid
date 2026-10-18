"""D-079: logistic_v2 becomes the default forecaster only where it was confirmed on unseen data."""

from __future__ import annotations

import json

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from blackgrid.prediction import rolling as R
from blackgrid.prediction import suite as suite_mod
from blackgrid.prediction.service import LinkPredictionArgs, PredictionTools, forecast
from blackgrid.prediction.synthetic import triadic_stream


def summary(improved: bool) -> dict:
    task = {"mean_ap": {"logistic_v2": 0.05, "recent_activity_product_2H": 0.02, "pair_recency": 0.03},
            "primary": {"model": "logistic_v2", "reference": "recent_activity_product_2H", "improved": improved,
                        "origins_won": 5 if improved else 2, "evaluable_origins": 5,
                        "ap_differences": {f"b{i}": 0.01 for i in range(5, 10)}}}
    rep = json.loads(json.dumps(task))
    rep["primary"]["reference"] = "pair_recency"
    return {"dataset": {"dataset_id": "fixture-unseen"}, "summary": {"new_pair": task, "repeat_pair": rep}}


@pytest.fixture(scope="module")
def setup(tmp_path_factory):
    root = tmp_path_factory.mktemp("promo")
    ev = triadic_stream(seed=9, nodes=50, events=2_000)
    evaluation = suite_mod.run(ev, root / "v1")
    (root / "rolling.json").write_text(json.dumps(summary(True)), encoding="utf-8")
    (root / "confirmed.json").write_text(json.dumps(summary(True)), encoding="utf-8")
    (root / "refuted.json").write_text(json.dumps(summary(False)), encoding="utf-8")
    return ev, evaluation, root


def tools(setup, confirmation: str) -> PredictionTools:
    ev, evaluation, root = setup
    return PredictionTools(ev, evaluation, rolling=root / "rolling.json", confirmation=root / confirmation,
                           model_cache=root / "models", data_sha256="fixture")


def test_cached_parameters_score_exactly_like_sklearn():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(400, 5)).astype(np.float32)
    y = x[:, 0] + rng.normal(size=400) > 0
    w = np.where(y, 1.0, 3.0)
    params = R.fit_logistic_params(x, y, w)
    scaler = StandardScaler().fit(x, sample_weight=w)
    ref = LogisticRegression(C=1.0, max_iter=300).fit(scaler.transform(x), y, sample_weight=w)
    assert np.allclose(R.score_logistic_params(params, x), ref.decision_function(scaler.transform(x)), atol=1e-5)


def test_promotion_requires_a_confirmed_result(setup):
    assert tools(setup, "confirmed.json").resolve_method("new_pair", "selected") == "logistic_v2"
    refuted = tools(setup, "refuted.json")
    assert refuted.resolve_method("new_pair", "selected") == refuted.selection["new_pair"]["temporal"]
    with pytest.raises(Exception, match="not registered"):
        refuted.resolve_method("new_pair", "logistic_v2")  # not even selectable without confirmation


def test_model_is_trained_once_then_reused_with_identical_scores(setup):
    first = tools(setup, "confirmed.json").link_prediction(LinkPredictionArgs(task="repeat_pair"))
    second = tools(setup, "confirmed.json").link_prediction(LinkPredictionArgs(task="repeat_pair"))
    assert first["method"] == "logistic_v2" and second["refit"]["cached_model"] is True
    assert first["refit"]["rows"] == second["refit"]["rows"]


def test_rolling_evidence_claims_pass_the_checker(setup, tmp_path):
    ev, evaluation, root = setup
    out = forecast(ev, evaluation, tmp_path / "f", "new_pair", rolling=root / "rolling.json",
                   confirmation=root / "confirmed.json", model_cache=root / "models")
    record = json.loads((out / "forecast.json").read_text(encoding="utf-8"))
    texts = [d["claim"]["text"] for d in record["decisions"]]
    assert record["compare"]["split"] == "rolling" and all(d["accepted"] for d in record["decisions"]), record["decisions"]
    assert any("won 5 of 5 windows" in t for t in texts)


def test_selected_forecasts_always_compare_against_their_own_evidence():
    from blackgrid.inquiry import validate_forecast

    plan = {"decision": "run", "tool_calls": [{"tool": "link_prediction", "args": {"task": "new_pair"}},
                                               {"tool": "prediction_compare", "args": {"task": "new_pair", "split": "test"}}]}
    ok, calls, _ = validate_forecast("Which pairs will message next?", {"family": "auto"}, plan)
    assert ok and calls[-1]["args"]["split"] == "rolling"  # the v1 test table describes other methods
    plan["tool_calls"][0]["args"]["method"] = "jaccard"
    assert validate_forecast("Which pairs will message next?", {"family": "auto"}, plan)[1][-1]["args"]["split"] == "test"


def test_mean_ap_difference_is_ap_evidence_and_upstreams_can_be_excluded(monkeypatch):
    import io

    from blackgrid import providers
    from blackgrid.prediction.claims import check

    scope = {"task": "new_pair", "cutoff": 1, "horizon_s": 1, "candidate_policy": "x", "split": "test", "method": "m"}
    claim = {"text": "The mean AP difference was 0.26.", "scope": scope, "evidence": ["c#/mean_ap_difference"]}
    assert check(claim, {"c#/mean_ap_difference": 0.2606}, scope) == []
    sent = {}

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake(request, timeout):
        sent.update(json.loads(request.data.decode("utf-8")))
        return Response(json.dumps({"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                                    "usage": {"prompt_tokens": 1, "completion_tokens": 1}}).encode())
    monkeypatch.setattr(providers.urllib.request, "urlopen", fake)
    providers.OpenRouterProvider("m", "sk-test", provider_ignore=("Wafer",)).complete("planner", {}, [], 100)
    assert sent["provider"] == {"require_parameters": True, "ignore": ["Wafer"]}
