"""Scientific invariants for the registered synthetic uncertainty/decision slice."""
import hashlib

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.stats import beta

from blackgrid.analysis.decisions import (BeliefSpec, Objective, Observation, ObservationStore,
                                         decide, loop, posterior, summarize)
from blackgrid.analysis.reliability import (CalibrationPartition, diagnostics, fit_sigmoid,
                                           interval_eligibility, paired_bootstrap, validate_partitions)
from blackgrid.analysis.causal import CausalReview, identify


def observation(i, success, action="A", spec=None):
    return Observation(identity=(spec or BeliefSpec()).identity, observation_id=str(i), action=action,
                       success=success, evidence_sha256=hashlib.sha256(str(i).encode()).hexdigest())


def test_exact_update_quantiles_and_integrated_predictive():
    spec = BeliefSpec()
    obs = [observation(0, True), observation(1, True), observation(2, False)]
    assert posterior(spec, obs, "A") == (3, 2)
    result = summarize(spec, obs)["methods"]["A"]
    assert result["mean"] == 0.6
    for q, value in zip([0.025, 0.975], result["credible_interval_95"]):
        assert quad(lambda x: 12 * x*x*(1-x), 0, value)[0] == pytest.approx(q)
    assert quad(lambda x: x * beta.pdf(x, 3, 2), 0, 1)[0] == pytest.approx(0.6)
    assert sum(result["predictive_block_10"]) == pytest.approx(1)


def test_evsi_hand_calculation_cost_stop_and_hard_budget():
    # Uniform priors: success -> max mean 2/3, failure -> choose other at 1/2.
    d = decide(BeliefSpec(), [], Objective())
    assert d["candidates"][0]["evsi"] == pytest.approx(0.5*(2/3)+0.5*0.5-0.5)
    assert d["action"] == "A"
    assert decide(BeliefSpec(), [], Objective(cost=0.1))["action"] == "stop"
    assert decide(BeliefSpec(), [], Objective(max_steps=0))["action"] == "stop"
    assert decide(BeliefSpec(), [], Objective(), feasible=())["action"] == "stop"
    with pytest.raises(ValueError):
        decide(BeliefSpec(), [], Objective(), feasible=("exec",))


def test_high_entropy_irrelevant_method_has_zero_decision_value():
    obs = [observation(i, True, "B") for i in range(9)]
    row = decide(BeliefSpec(), obs, Objective())["candidates"][0]
    assert row["evsi"] == 0  # A still uniform, but cannot beat B with one observation


def test_deduplication_identity_and_bounded_loop(tmp_path):
    store = ObservationStore(tmp_path / "observations.sqlite")
    obs = observation(0, True)
    assert store.add(obs) and not store.add(obs)
    with pytest.raises(ValueError):
        store.add(observation(0, False))
    with pytest.raises(ValueError):
        posterior(BeliefSpec(alpha=2), [obs], "A")
    trace = loop(BeliefSpec(), Objective(), lambda a, i: observation(i, i % 2 == 0, a), store)
    assert trace[-1]["action"] == "stop" and len(store.read()) <= 10
    before = len(store.read())
    loop(BeliefSpec(), Objective(), lambda *args: pytest.fail("replay requested another observation"), store)
    assert len(store.read()) == before


def test_calibration_partition_isolation_and_metrics():
    fit = CalibrationPartition("fit", 2, 3, np.array([-2., -1., 1., 2.]), np.array([0, 0, 1, 1]))
    model = fit_sigmoid(fit)
    coef = model.coef_.copy()
    assessment = CalibrationPartition("assessment", 3, 4, fit.scores, 1-fit.labels)
    with pytest.raises(ValueError):
        fit_sigmoid(assessment)
    assert np.array_equal(model.coef_, coef)
    parts = [CalibrationPartition(role, i, i+1, fit.scores, fit.labels) for i, role in
             enumerate(["train", "selection", "fit", "assessment", "test"])]
    validate_partitions(parts)
    with pytest.raises(ValueError):
        validate_partitions(parts[::-1])
    d = diagnostics([0.25, 0.75], [0, 1])
    assert d["brier"] == 0.0625 and d["log_loss"] == pytest.approx(-np.log(0.75))
    assert sum(b["count"] for b in d["bins"]) == 2 and not d["probability_display"]
    assert diagnostics([0.1], [0])["average_precision"] is None


def test_graph_units_and_real_window_interval_refusal():
    assert not interval_eligibility("time_window", 2)["eligible"]
    assert not interval_eligibility("pair", 100000, independent=True)["eligible"]
    with pytest.raises(ValueError):
        paired_bootstrap(np.ones(30))
    result = paired_bootstrap(np.ones(30)*0.2, independent=True)
    assert result["interval"] == pytest.approx([0.2, 0.2])


def causal_spec(**changes):
    defaults = dict(treatment="T", outcome="Y", unit="graph", population="synthetic graphs",
                    edges=(("X", "T"), ("X", "Y"), ("T", "Y")), adjustment=("X",),
                    observed=("T", "Y", "X"), provenance="registered synthetic equations", synthetic=True,
                    time_order=True, consistency=True, positivity=True, no_hidden_confounding=True,
                    no_selection_bias=True, no_interference=True, measurement_valid=True)
    return CausalReview(**(defaults | changes))


def test_causal_valid_and_refusal_fixtures():
    assert identify(causal_spec())["verdict"] == "simulated intervention only"
    for changes in [dict(positivity=False), dict(no_hidden_confounding=False), dict(no_interference=False),
                    dict(adjustment=()), dict(edges=(("T", "C"), ("Y", "C")), adjustment=("C",),
                                              observed=("T", "Y", "C"))]:
        assert identify(causal_spec(**changes))["verdict"] == "not identified"


@pytest.fixture(scope="module")
def research_run(tmp_path_factory):
    from blackgrid.evaluation.sprint7 import run
    path = tmp_path_factory.mktemp("s7") / "demo"
    result = run(path)
    assert result["status"] == "completed"
    return path


def test_full_loop_replay_and_registered_tools(research_run):
    from blackgrid.agent.research import ResearchTools
    from blackgrid.evaluation.sprint7 import verify
    before = (research_run / "belief.sqlite").read_bytes()
    assert verify(research_run)["status"] == "verified"
    tools = ResearchTools(research_run)
    assert tools.call({"tool": "reliability_audit"})["probability_display"] is False
    assert "unavailable" in tools.call({"tool": "experiment_decision"})["real_forecast_voi"]
    for raw in [{"tool": "exec"}, {"tool": "belief_update", "success": True},
                {"tool": "experiment_decision", "cost": 0}, {"tool": "belief_update", "path": "truth"}]:
        with pytest.raises(ValueError):
            tools.call(raw)
    assert (research_run / "belief.sqlite").read_bytes() == before


def test_artifact_tamper_and_missing_evidence_fail_closed(research_run, tmp_path):
    import shutil
    from blackgrid.evaluation.sprint7 import verify
    path = tmp_path / "copy"
    shutil.copytree(research_run, path)
    (path / "beliefs.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        verify(path)


def test_claim_vocabulary_rejects_invented_probability_and_interval_labels():
    from blackgrid.agent.research import checked_claim
    evidence = {"beliefs.json": {"methods": {"A": {"mean": 0.5}}}}
    assert checked_claim("posterior_mean_A", 0.5, evidence)["scope"] == "registered synthetic model only"
    for kind, value in [("posterior_mean_A", 0.9), ("individual_probability", 0.5),
                        ("bayesian_bootstrap_credible_interval", [0, 1]), ("identified_real_influence", 2)]:
        with pytest.raises(ValueError):
            checked_claim(kind, value, evidence)


def test_cancel_and_memory_limit_preserve_failure(tmp_path, monkeypatch):
    import blackgrid.evaluation.sprint7 as s7
    path = tmp_path / "cancel"
    path.mkdir()
    (path / "CANCEL").touch()
    with pytest.raises(InterruptedError):
        s7.Guard(path).check()
    monkeypatch.setattr(s7, "peak_memory_bytes", lambda: 3 * 1024**3)
    out = tmp_path / "failed"
    result = s7.run(out)
    assert result["status"] == "failed" and result["failure"] == "MemoryError"
    assert (out / "sprint7_manifest.json").exists()


def test_posterior_predictive_misfit_and_degenerate_calibration():
    from blackgrid.analysis.decisions import predictive_check
    assert predictive_check(100, 1, 0, 10)["limitation"] == "predictive misfit: stop"
    with pytest.raises(ValueError):
        fit_sigmoid(CalibrationPartition("fit", 2, 3, np.arange(5.), np.zeros(5)))


def test_console_payload_has_scientific_sections(research_run):
    from blackgrid.console.data import run_payload
    from blackgrid.console.render import page
    payload = run_payload(research_run.parent, research_run)
    assert payload["beliefs"]["observations"] == 1
    assert payload["causal"]["collegemsg"]["verdict"] == "not identified"
    html = page({"mode": "static", "view": "run", "payload": payload, "base": "../"})
    assert "renderDecisions" in html and "Next experiment" in html
