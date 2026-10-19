"""Opt-in paid UI, retained ceilings and independent prior-spend accounting."""
import json

import pytest

from blackgrid.agent.budget import BudgetExceeded, BudgetLedger, Pricing
from blackgrid.contracts import RunConfig
from blackgrid.console.server import Console
from blackgrid.agent.live_allowance import constrain, ensure_allowance, project_spend, read_allowance
from blackgrid.workflow.api import open_services


def config():
    return RunConfig.model_validate({"mode":"live", "paid_execution_authorized":True,
        "dataset":{"dataset_id":"fixture", "path":"benchmarks/dev", "sha256":"0"*64,
        "source_url":"local-synthetic", "citations":["Independent fixture"],
        "rights_status":"accepted_local_noncommercial", "rights_decision":"fixture"},
        "llm":{"max_tokens_per_call":16000, "reasoning_max_tokens":12000}})


def add_spend(runs, usd, source):
    services=open_services(runs)
    try: services.store.import_prior_spend(source, "sprint2", usd)
    finally: services.close()


def test_restart_retains_ceiling_and_counts_other_spend(tmp_path):
    add_spend(tmp_path, .12, "prior")
    path=ensure_allowance(tmp_path)
    original=json.loads(path.read_text())
    add_spend(tmp_path, .07, "after")
    assert ensure_allowance(tmp_path)==path
    assert json.loads(path.read_text())==original
    assert read_allowance(path,tmp_path)["remaining_usd"]==pytest.approx(.43)
    bounded=constrain(config(),path,tmp_path)
    assert bounded.budget.max_usd_total==pytest.approx(.62)
    assert bounded.budget.max_usd_per_investigation==pytest.approx(.15)
    assert bounded.llm.reasoning_max_tokens==12000


@pytest.mark.parametrize('reasoning',[0,1024])
def test_allowance_never_increases_an_explicit_reasoning_budget(tmp_path,reasoning):
    path=ensure_allowance(tmp_path)
    cfg=config().model_copy(update={'llm':config().llm.model_copy(update={'max_tokens_per_call':4096,'reasoning_max_tokens':reasoning})})
    assert constrain(cfg,path,tmp_path).llm.reasoning_max_tokens==reasoning


def test_exhaustion_and_reservations_stop_before_dispatch(tmp_path):
    path=ensure_allowance(tmp_path)
    add_spend(tmp_path,.49,"spent")
    bounded=constrain(config(),path,tmp_path)
    assert bounded.budget.max_usd_per_investigation==pytest.approx(.01)
    ledger=BudgetLedger(bounded.budget,Pricing(model="fake",prompt_usd_per_token=.001,
        completion_usd_per_token=.001,source="fixture",fetched_utc="fixture"),other_runs_usd=project_spend(tmp_path))
    with pytest.raises(BudgetExceeded): ledger.reserve("x",16000)
    add_spend(tmp_path,.01,"exhausted")
    with pytest.raises(ValueError,match="exhausted"): constrain(config(),path,tmp_path)


def test_default_console_denies_paid_but_authorized_console_uses_allowance(tmp_path):
    con=Console(tmp_path,tmp_path/"cache",tmp_path/"configs"/"collegemsg_sprint01.json",tmp_path,8765)
    body={"action":"start","mode":"live","question":"Which nodes have high betweenness?"}
    with pytest.raises(ValueError): con.argv(body)
    con.live_allowance=ensure_allowance(tmp_path)
    argv=con.argv(body)
    assert "--allow-paid" in argv and "--live-allowance" in argv
    assert argv[argv.index("--mode")+1]=="live"
    assert argv[argv.index("--planning-mode")+1]=="single"
    assert con.argv(body | {"adaptive":True})[-2:]==["--question",body["question"]]
    add_spend(tmp_path,.5,"exhausted")
    with pytest.raises(ValueError,match="exhausted"): con.argv(body)


def test_mismatched_or_tampered_allowance_is_not_renewed(tmp_path):
    path=ensure_allowance(tmp_path)
    data=json.loads(path.read_text());data["cap_usd"]=5
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError): ensure_allowance(tmp_path)
    assert json.loads(path.read_text())["cap_usd"]==5  # rejected, never silently replaced


def test_pilot_requires_explicit_paid_authorization(tmp_path):
    from blackgrid.evaluation.sprint5_live import run_pilot
    with pytest.raises(PermissionError): run_pilot(tmp_path/"trial")
    assert not (tmp_path/"trial").exists()


def test_bridge_plan_can_include_supplementary_centrality():
    from blackgrid.agent.inquiry import validate_structural
    ok, calls, _ = validate_structural("Which nodes connect groups and are rankings stable?", {"family":"bridge"},
        {"decision":"run","tool_calls":[{"tool":"community_partition","args":{}},{"tool":"node_centrality","args":{}}]})
    assert ok and {c["tool"] for c in calls}=={"community_partition","node_centrality","community_bridge","ranking_sensitivity"}
