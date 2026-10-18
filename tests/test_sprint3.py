"""Sprint 3 scientific invariants and independent evaluator failure checks."""
from __future__ import annotations

import ast
import hashlib
import json
import time
from pathlib import Path

import networkx as nx
import pytest
from pydantic import ValidationError

from blackgrid.benchmark import dev_cases
from blackgrid.contracts import canonical_sha256
from blackgrid.evaluation import (PREFIX, assess_claim, numerical_verdict, paired_interval,
                                  evaluate_run, failure_row, resolve, summarize, verify_artifacts)
from blackgrid.experiment import DeadlineExceeded, modularity, run_community_test
from blackgrid.methods import (MethodSpec, compare_scope, comparison_verdict, optimize,
                               validate_partition, variation_information)
from blackgrid.validation import CASE_IDS, public_registry, validation_input, validation_spec


def test_fresh_inputs_reproducible_disjoint_and_answer_free():
    registry = public_registry()
    hashes = [c["projection_sha256"] for c in registry["cases"]]
    assert len(hashes) == len(set(hashes)) == 24
    assert not set(hashes) & {c.record.projection_sha256 for c in dev_cases().values()}
    assert registry == public_registry()
    for cid in CASE_IDS:
        case = validation_input(cid)
        assert not case.graph.graph and not any(d for _, d in case.graph.nodes(data=True))
        assert not any(d for _, _, d in case.graph.edges(data=True))
        text = case.public.model_dump_json() + case.record.model_dump_json()
        for forbidden in ("p_in", "p_out", "planted_labels", "hidden_edges", "acceptable_verdicts", "rationale"):
            assert forbidden not in text
        assert validation_spec(cid).sensitivity.replicates == 3
    with pytest.raises(ValueError):
        validation_input("test-001")


def test_independent_evaluator_does_not_import_critic_or_pilot():
    import blackgrid.evaluation as evaluator

    tree = ast.parse(Path(evaluator.__file__).read_text())
    modules = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any("critic" in (m or "") or "pilot" in (m or "") for m in modules)


def test_method_contract_rejects_adaptive_effort_changes():
    with pytest.raises(ValidationError):
        MethodSpec(null_replicates=19)
    with pytest.raises(ValidationError):
        MethodSpec(restarts=10)


@pytest.mark.parametrize("method", ["louvain", "leiden"])
def test_adapters_preserve_nonconsecutive_nodes_isolates_and_known_modularity(method):
    if method == "leiden":
        pytest.importorskip("leidenalg")
    graph = nx.disjoint_union(nx.complete_graph(3), nx.complete_graph(3))
    graph.add_node(6)
    graph = nx.relabel_nodes(graph, {i: i * 100 + 9 for i in graph})
    result = optimize(graph, method, 31)
    assert validate_partition(graph, result.parts) == 0
    assert result.q == pytest.approx(.5, abs=1e-12)
    assert result.q == pytest.approx(modularity(graph, result.parts), abs=1e-12)
    again = optimize(graph, method, 31)
    assert again.q == result.q and again.parts == result.parts
    with pytest.raises(DeadlineExceeded):
        optimize(graph, method, 31, deadline=time.perf_counter() - 1)
    with pytest.raises(ValueError, match="unknown"):
        optimize(graph, "fake-leiden", 31)


def test_partition_validation_and_stability_oracles():
    graph = nx.path_graph(4)
    with pytest.raises(ValueError, match="exactly once"):
        validate_partition(graph, [{0, 1}, {1, 2, 3}])
    with pytest.raises(ValueError, match="exactly once"):
        validate_partition(graph, [{0, 1}, {2}])
    assert validate_partition(graph, [{0, 2}, {1, 3}]) == 2
    assert variation_information([{0, 1}, {2, 3}], [{2, 3}, {0, 1}]) == pytest.approx(0)
    assert variation_information([{0, 1}, {2, 3}], [{0, 2}, {1, 3}]) == pytest.approx(2 * __import__("math").log(2))


def test_shared_nulls_and_degree_preservation(monkeypatch):
    import blackgrid.methods as methods

    seen = {m: [] for m in ("louvain", "leiden")}
    original = methods.optimize
    graph = nx.gnm_random_graph(12, 25, seed=11)

    def observed(g, method, *args, **kwargs):
        seen[method].append(set(map(frozenset, g.edges())))
        assert dict(g.degree()) == dict(graph.degree())
        # Exercise the real common scorer; no optional backend is needed for this oracle.
        return original(g, "louvain", *args, restarts=1, **kwargs)
    monkeypatch.setattr(methods, "optimize", observed)
    report = compare_scope(graph, 31, "whole_graph", MethodSpec())
    assert seen["louvain"] == seen["leiden"] and len(seen["louvain"]) == 100
    assert len(report["null_hashes"]) == 99
    for method in seen:
        result = report["methods"][method]
        assert result["p_value"] == (1 + result["exceedances"]) / 100


def test_disconnected_verdict_needs_component_and_missingness_qualification():
    primary = {"status": "completed", "methods": {"leiden": {"p_value": .01}}}
    assert comparison_verdict(primary, None, False, "leiden") == "inconclusive"
    assert comparison_verdict(primary, primary, False, "leiden") == "supported"
    assert comparison_verdict(primary, primary, False, "leiden", 3) == "inconclusive"
    assert comparison_verdict({"status": "abstained"}, None, True, "leiden") == "abstain"


@pytest.fixture
def documents():
    from tests.test_experiment import spec

    config = spec()
    report = run_community_test(dev_cases()["dev-002"].graph, config,
                                spec_sha256=canonical_sha256(config)).model_dump(mode="json")
    return {"experiment_report.json": report}


def test_independent_pvalue_oracle_rejects_tampering(documents):
    report = documents["experiment_report.json"]
    assert numerical_verdict(report) == report["verdict"]
    report["primary"]["result"]["p_value"] = .0001
    with pytest.raises(ValueError, match="inconsistent"):
        numerical_verdict(report)


def test_scoring_checks_numeric_meanings_citations_causality_and_unknown_text(documents):
    r = documents["experiment_report.json"]["primary"]["result"]
    text = f"Modularity Q = {r['observed_statistic']:.3f} versus a degree-preserving null mean of {r['null']['mean']:.3f} (p = {r['p_value']:.3f})."
    claim = {"text": text, "evidence_level": "descriptive",
             "evidence": [PREFIX + x for x in ("observed_statistic", "null/mean", "p_value")]}
    assert assess_claim(claim, documents)[0] == "supported"
    assert assess_claim({**claim, "evidence": claim["evidence"][:-1]}, documents)[0] == "unsupported"
    assert assess_claim({**claim, "text": text.replace(f"Q = {r['observed_statistic']:.3f}", "Q = 99.999")}, documents)[0] == "unsupported"
    assert assess_claim({**claim, "text": "Nodes cause community structure."}, documents)[0] == "unsupported"
    assert assess_claim({**claim, "text": "These nodes cannot cause a known effect."}, documents)[0] == "unassessed"
    assert assess_claim({**claim, "text": "An unseen scientific claim."}, documents)[0] == "unassessed"
    assert assess_claim({**claim, "text": "The network has strong community structure (modularity Q = 0.9)."}, documents)[0] == "unsupported"


def test_json_pointer_and_manifest_integrity(tmp_path):
    assert resolve({"a.json": {"x/y": [3]}}, "a.json#/x~1y/0") == 3
    artifacts = {}
    for name in ("investigation.json", "config.json", "graph_record.json"):
        p = tmp_path / name
        p.write_text("{}")
        artifacts[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    (tmp_path / "manifest.json").write_text(json.dumps({"artifacts": artifacts}))
    assert len(verify_artifacts(tmp_path)) == 3
    (tmp_path / "investigation.json").write_text('{"tampered":true}')
    with pytest.raises(ValueError, match="integrity"):
        verify_artifacts(tmp_path)


def test_paired_graph_interval_not_claim_level():
    result = paired_interval([1., 1., 1.])
    assert result["n"] == 3 and result["ci95"] == [1., 1.]
    assert paired_interval([])["ci95"] is None


def test_causal_refusal_is_distinct_from_descriptive_graph_verdict(tmp_path, documents):
    report = documents["experiment_report.json"]
    docs = {**documents, "config.json": {}, "graph_record.json": {"edge_status_counts": {}},
            "sensitivity.json": {}, "investigation.json": {
                "status": "completed", "condition": "tool_only", "reported_claims": [],
                "verdict": report["verdict"], "flags": report["flags"], "missing_analyses": [],
                "cost": {"llm_calls": 2, "input_tokens": 20, "output_tokens": 10, "actual_usd": 0}}}
    artifacts = {}
    for name, payload in docs.items():
        p = tmp_path / name
        p.write_text(json.dumps(payload))
        artifacts[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = {"status": "completed", "artifacts": artifacts}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    row, _ = evaluate_run(tmp_path, "val-020")
    assert row["evidence_verdict"] == "rejected" and not row["evidence_consistent"]
    assert not row["useful"] and row["complete"]
    manifest["status"] = "failed"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    assert not evaluate_run(tmp_path, "val-020")[0]["complete"]


def test_unscorable_attempts_stay_in_denominators_with_unknown_counts():
    rows = [failure_row("val-001", c) for c in ("tool_only", "validated")]
    summary = summarize(rows)
    assert summary["tool_only"]["cases"] == 1
    assert summary["tool_only"]["unscored_cases"] == summary["tool_only"]["usage_unknown_cases"] == 1
    assert summary["paired_validated_minus_tool_only"]["useful_fraction"]["n"] == 1


def test_suite_refuses_outside_runs_and_invalid_spec_reload(tmp_path, capsys):
    from blackgrid.cli import EXIT_INVALID, main
    from blackgrid.runner import load_input

    assert main(["sprint3", "--output", str(tmp_path / "unsafe")]) == EXIT_INVALID
    with pytest.raises(ValueError):
        load_input({"kind": "validation", "case_id": "test-001"}, tmp_path)
    inp = load_input({"kind": "validation", "case_id": "val-019"}, tmp_path)
    assert inp.case_id == "val-019" and not hasattr(inp, "key")


def test_suite_budget_failure_is_preserved_and_output_cannot_be_reused(tmp_path, monkeypatch):
    import blackgrid.sprint3 as sprint3

    monkeypatch.setattr(sprint3, "TOTAL_TIMEOUT_S", -1)
    monkeypatch.setattr(sprint3, "run_investigation", lambda *_a, **_k: pytest.fail("budget must stop execution"))
    output = sprint3.run_suite(tmp_path / "expired")
    record = json.loads((output / "suite.json").read_text())
    assert record["status"] == "failed" and record["agent_runs"] == record["method_runs"] == 0
    assert "budget exhausted" in record["errors"][0]["error"]
    assert json.loads((output / "attempts.jsonl").read_text())["state"] == "failed"
    saved = (output / "suite.json").read_bytes()
    with pytest.raises(FileExistsError):
        sprint3.run_suite(output)
    assert (output / "suite.json").read_bytes() == saved
