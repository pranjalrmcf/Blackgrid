"""Synthetic provenance, protected truth, known numerical summaries and stop limits."""
import json
import sys
from pathlib import Path
import pytest
from blackgrid.contracts import DataOrigin, RunConfig
from blackgrid.data.collegemsg import build_graph
from blackgrid.workflow.runner import make_provider
from blackgrid.agent.providers import MockProvider
from scripts.generate_phase6 import generate
from benchmarks.production.common import quantiles, stop_reason
from tests.test_deployment import settings
from tests.test_monitoring import OPS
from tests.test_api import headers
from blackgrid.operations.api import create_app
from fastapi.testclient import TestClient


def test_generators_are_deterministic_bounded_and_truth_separated(tmp_path):
    a,b = tmp_path/"a", tmp_path/"b"
    first, second = generate(a, sizes=(30,)), generate(b, sizes=(30,))
    assert first == second and len(first) == 5
    for config_path in (a/"public").glob("*.json"):
        if config_path.name.endswith(".manifest.json"): continue
        config = RunConfig.model_validate_json(config_path.read_bytes())
        built = build_graph(a/"public",config)
        assert built.record.origin is DataOrigin.SYNTHETIC
        assert built.record.source is None and built.record.generator_sha256
        assert "stochastic" not in built.record.graph_id
        assert len(built.graph) <= 30 and built.graph.number_of_edges() <= 10000
        assert "planted_membership" not in json.dumps(built.record.model_dump(mode="json"))
    future = json.loads((a/"truth/temporal-30.json").read_text())
    assert all(t >= future["future_cutoff"] for _,_,t in future["future_events"])
    assert not (a/"public/truth").exists()
    assert not any("future_events" in p.read_text() for p in (a/"public").iterdir())
    with pytest.raises(ValueError): generate(a)
    with pytest.raises(ValueError): generate(tmp_path/"large", sizes=(1001,))


def test_synthetic_manifest_tampering_fails_and_default_mock_stays_unchanged(tmp_path, settings, monkeypatch):
    root = tmp_path/"generated"
    generate(root,sizes=(30,))
    config = RunConfig.model_validate_json((root/"public/stochastic_block-30.json").read_bytes())
    manifest = root/"public/stochastic_block-30.events.manifest.json"
    manifest.write_text(manifest.read_text()+" ")
    with pytest.raises(ValueError, match="provenance"):
        build_graph(root/"public",config)
    baseline = RunConfig.model_validate_json(settings.config.read_bytes())
    monkeypatch.delenv("BLACKGRID_BENCHMARK_MOCK_PROFILE",raising=False)
    assert type(make_provider(baseline,allow_paid=False,replay_from=None,env_file=tmp_path/"absent")) is MockProvider
    monkeypatch.setenv("BLACKGRID_BENCHMARK_MOCK_PROFILE","latency")
    with pytest.raises(ValueError, match="synthetic"):
        make_provider(baseline,allow_paid=False,replay_from=None,env_file=tmp_path/"absent")


def test_quantiles_and_resource_stops_have_independent_known_answers():
    result = quantiles(list(range(1,101)))
    assert result == {"samples":100,"p50":50,"p95":95,"p99":99}
    assert quantiles([])["p95"] is None
    with pytest.raises(ValueError): quantiles([float("nan")])
    protocol = {"target_memory_stop_bytes":100,"target_pids_stop":20,"disk_free_stop_bytes":10}
    assert stop_reason({"memory_current_bytes":100},protocol) == "resource_threshold"
    assert stop_reason({"pids_current":21},protocol) == "resource_threshold"
    assert stop_reason({"disk_free_bytes":9},protocol) == "storage_threshold"
    assert stop_reason({"memory_current_bytes":90,"disk_free_bytes":20},protocol) is None


@pytest.mark.skipif(sys.platform != "linux", reason="real contained synthetic worker")
@pytest.mark.parametrize("question,family", [("Which nodes have the highest degree and betweenness?","centrality"),
    ("Cluster behavioral profiles and find unusual activity candidates.","behavior")])
def test_actual_api_worker_keeps_synthetic_origin_and_never_reads_truth(tmp_path, settings,question,family):
    root = tmp_path/"synthetic"
    generate(root,sizes=(100,))
    configured = settings.model_copy(update={"environment":"test", "benchmark_mock_profile":"latency",
        "config":root/"public/stochastic_block-100.json", "data_root":root/"public"})
    with TestClient(create_app(configured,OPS),base_url="http://127.0.0.1") as client:
        identity = client.get("/api/v1/benchmark/identity",headers=headers()).json()
        assert identity["origin"] == "synthetic" and not identity["live_enabled"]
        job = client.post("/api/v1/jobs",json={"question":question},headers=headers()).json()["job_id"]
        client.app.state.jobs.worker.join(40)
        assert not client.app.state.jobs.worker.is_alive()
        row = client.get(f"/api/v1/jobs/{job}",headers=headers()).json()
        assert row["state"] == "completed",row
        result = client.get(f"/api/v1/jobs/{job}/results",headers=headers()).json()
        assert result["summary"]["actual_usd"] == 0 and result["family"] == family
        folder = client.app.state.jobs.run_folder("alice",job)
        record = json.loads((folder/"graph_record.json").read_bytes())
        assert record["origin"] == "synthetic" and record["source"] is None
        trace = (folder/"llm_trace.jsonl").read_text()
        assert "planted_membership" not in trace and "future_events" not in trace and "stochastic_block" not in trace


def test_benchmark_latency_flag_cannot_enable_on_production_real_data(settings):
    bad = settings.model_copy(update={"benchmark_mock_profile":"latency"})
    with pytest.raises(ValueError,match="isolated synthetic"):
        with TestClient(create_app(bad,OPS),base_url="http://127.0.0.1"):
            pass
