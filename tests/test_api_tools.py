"""Automatic API routing through real contained workers, with fixture-only LLM transport."""
from __future__ import annotations

import hashlib
import json
import sys
from contextlib import closing

import networkx as nx
import pytest
from fastapi.testclient import TestClient

from blackgrid.agent.providers import MockProvider
from blackgrid.agent.roles import SYSTEM
from blackgrid.agent.tools import TOOLS
from blackgrid.operations.api import create_app
from blackgrid.operations.api_jobs import Jobs
from blackgrid.operations.api_tools import CATALOG
from tests.test_api import CREDS, headers
from tests.test_api_live import policy
from tests.test_deployment import settings


@pytest.fixture
def environment(settings, policy, tmp_path, monkeypatch):
    from blackgrid.evaluation.sprint7 import run
    graph = nx.karate_club_graph()
    events = settings.data_root / "events.txt"
    events.write_text("".join(f"{a+1000001} {b+1000001} {100+i}\n" for i, (a,b) in enumerate(graph.edges())))
    digest = hashlib.sha256(events.read_bytes()).hexdigest()
    for path in (settings.config, policy.config):
        raw = json.loads(path.read_bytes())
        raw["dataset"]["sha256"] = digest
        raw["experiment"].update(null_replicates=19, optimizer_restarts=1)
        raw["experiment"]["sensitivity"]["replicates"] = 1
        path.write_text(json.dumps(raw))
    root = tmp_path / "evidence"
    prediction = root / "prediction"
    prediction.mkdir(parents=True)
    tasks = {"new_pair": "resource_allocation", "repeat_pair": "pair_frequency"}
    # Explicit test fixtures, not measured evaluation results or a benchmark.
    fixtures = {
        "selection.json": {"selection": {task: {"temporal": method, "static_reference": method} for task, method in tasks.items()}},
        "freeze.json": {"data_sha256": digest, "fixture": True},
        "validation.json": {task: {"table": {method: {"mean_ap": .1}}} for task, method in tasks.items()},
        "predictions_manifest.json": {"fixture": True},
        "test_evaluation.json": {"test": {task: {"cutoffs": {"b8": {"methods": {method: {"average_precision": .1}},
            "manifest": {"prevalence": .01}}}, "mean_ap_difference": 0} for task, method in tasks.items()}},
    }
    for name, data in fixtures.items():
        (prediction / name).write_text(json.dumps(data))
    assert run(root / "research")["status"] == "completed"
    plans, calls = {}, []
    def fake(payload, policy):
        from blackgrid.agent.inquiry import family
        if payload["method"] == "GET":
            return {"ok": True, "response": {"data": [{"id": policy.model,
                "pricing": {"prompt": "0.0000001", "completion": "0.0000001"}}]}}
        messages = payload["body"]["messages"]
        role = next(role for role, system in SYSTEM.items() if messages[0]["content"] == system)
        data = json.loads(messages[1]["content"])
        assert "1000001" not in json.dumps(data), "node identifiers reached a model prompt"
        calls.append(role)
        answer = MockProvider().complete(role, data, messages, 1000).text
        if role == "planner":
            question = data["task"]["question"]
            answer = plans.get(question, json.loads(answer))
            answer.setdefault("family", family(question, data["task"]["request"]))
            if answer["family"] == "forecast":
                answer["tool_calls"].insert(0, {"tool": "temporal_profile", "args": {}})
            answer = json.dumps(answer)
        return {"ok": True, "response": {"model": policy.model,
            "choices": [{"message": {"content": answer}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 20, "cost": .000004}}}
    monkeypatch.setattr("blackgrid.operations.live.broker_request", fake)
    return settings.model_copy(update={"evidence_root": root}), plans, calls


def ask(client, question, key, live=True):
    body = {"question": question, "mode": "live", "allow_paid": True} if live else {"question": question}
    reply = client.post("/api/v1/jobs", json=body, headers=headers(key=key))
    assert reply.status_code == 202, reply.text
    job = reply.json()["job_id"]
    client.app.state.jobs.worker.join(40)
    assert not client.app.state.jobs.worker.is_alive()
    status = client.get(f"/api/v1/jobs/{job}", headers=headers()).json()
    reply = client.get(f"/api/v1/jobs/{job}/results", headers=headers())
    assert reply.status_code == 200, (status, reply.text)
    return status, reply.json()


def test_catalog_exactly_matches_registered_tools_and_requires_auth(settings):
    assert set(CATALOG) == set(TOOLS) and len(CATALOG) == 18
    with TestClient(create_app(settings, CREDS), base_url="http://127.0.0.1") as client:
        assert client.get("/api/v1/capabilities").status_code == 401
        catalog = client.get("/api/v1/capabilities", headers=headers()).json()
        assert catalog["routing"] == "auto" and len(catalog["tools"]) == 18
        assert not any(t["available"] for t in catalog["tools"] if t["family"] in ("forecast", "research"))


@pytest.mark.skipif(sys.platform != "linux", reason="fixture LLM broker uses Linux containment")
def test_all_18_tools_through_authenticated_api_and_contained_workers(environment):
    configured, _, calls = environment
    questions = {
        "community": "Is community structure stronger than expected from node degrees?",
        "centrality": "Which nodes have highest degree and betweenness, and are those rankings stable?",
        "bridge": "Which nodes bridge communities, and are those rankings robust?",
        "behavior": "Cluster behavioral profiles, find similar users and unusual activity candidates.",
        "forecast": "Which pairs who have never messaged will message next month, and how reliable is the ranking?",
        "research": "Review Sprint 7 uncertainty, posterior beliefs, next experiment and causal identification.",
    }
    seen = set()
    with TestClient(create_app(configured, CREDS), base_url="http://127.0.0.1") as client:
        assert all(t["available"] for t in client.get("/api/v1/capabilities", headers=headers()).json()["tools"])
        for family, question in questions.items():
            status, result = ask(client, question, family)
            assert status["state"] == "completed", (family, status)
            assert result["family"] == family and result["analyses"]
            assert "1000001" not in json.dumps(result)
            assert '"rows"' not in json.dumps(result) and "local_ranking" not in json.dumps(result)
            seen.update(result["analyses"])
            progress_tools = {entry["tool"] for entry in status["progress"]["tools"]}
            assert set(result["analyses"]) <= progress_tools
            if family != "community":
                assert "p_value" not in result["summary"] and result["conclusions"], result
            if family == "forecast":
                assert result["claim_type"] == "predictive" and "full validated observed history" in result["scope"]
            if family == "research":
                assert "synthetic" in result["scope"]
                assert result["research_verification_profile"] == "api-beliefs-portability-v1"
                assert result["analyses"]["causal_identification_check"]["summary"]["real_verdict"] == "not identified"
        assert seen == set(TOOLS), set(TOOLS) - seen
        assert calls.count("planner") == len(questions)


@pytest.mark.skipif(sys.platform != "linux", reason="fixture LLM broker uses Linux containment")
def test_semantic_agent_choice_for_question_without_routing_keywords(environment):
    configured, plans, _ = environment
    question = "Describe the busiest connectors."
    plans[question] = {"decision": "run", "family": "centrality", "tool_calls": [{"tool": "node_centrality", "args": {}}]}
    with TestClient(create_app(configured, CREDS), base_url="http://127.0.0.1") as client:
        status, result = ask(client, question, "semantic")
        assert status["state"] == "completed" and result["family"] == "centrality"
        assert "node_centrality" in result["analyses"] and "community_test" not in result["analyses"]


def test_missing_forecast_evidence_returns_partial_without_community_substitution(settings):
    with TestClient(create_app(settings, CREDS), base_url="http://127.0.0.1") as client:
        status, result = ask(client, "Which pairs will message next month?", "missing", live=False)
        assert status["state"] == "partial" and result["family"] == "forecast"
        assert "link_prediction" in result["missing_analyses"] and not result["analyses"]


def test_existing_queued_request_retains_community_routing_after_migration(settings, monkeypatch):
    monkeypatch.setattr(Jobs, "kick", lambda self: None)
    jobs = Jobs(settings)
    try:
        with closing(jobs.db()) as db, db:
            db.execute("INSERT INTO jobs(id,owner,idem,digest,state,created) VALUES(?,?,?,?,?,?)",
                ("c"*32, "alice", "legacy", "digest", "queued", "fixture"))
        assert jobs.row("alice", "c"*32)["routing"] == "community"
    finally:
        jobs.close()


def test_forecast_evidence_from_another_event_source_is_rejected(environment):
    configured, _, _ = environment
    freeze = configured.evidence_root / "prediction/freeze.json"
    freeze.write_text(json.dumps({"data_sha256": "0" * 64}))
    with TestClient(create_app(configured, CREDS), base_url="http://127.0.0.1") as client:
        status, result = ask(client, "Which pairs will message next month?", "wrong-source", live=False)
        assert status["state"] == "partial" and "link_prediction" in result["missing_analyses"]
        assert not result["conclusions"] and "link_prediction" not in result["analyses"]


def test_aggregate_projection_does_not_export_private_or_unknown_fields():
    from blackgrid.operations.api_tools import aggregate
    source = {"summary": {"max_degree": 9, "new_private_field": "PRIVATE_NODE"},
              "rows": [{"node": "PRIVATE_NODE"}], "coefficients": [1, 2]}
    assert aggregate("node_centrality", source) == {"max_degree": 9}


def test_research_read_only_observations_never_create_or_write_database(tmp_path):
    import sqlite3
    from blackgrid.analysis.decisions import ObservationStore
    path = tmp_path / "absent.sqlite"
    store = ObservationStore(path, read_only=True)
    with pytest.raises(sqlite3.OperationalError):
        store.read()
    with pytest.raises(ValueError, match="read-only"):
        store.add(None)
    assert not path.exists()
