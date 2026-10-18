"""Reproduce the saved v2 live pilot with recorded responses only; no network or payment."""
import json
import sys
from pathlib import Path

from blackgrid.contracts import RunConfig
from blackgrid.providers import ReplayProvider
from blackgrid.runner import REPO_ROOT, run_investigation, write_json
from blackgrid.sprint5 import score
from blackgrid.sprint5_live import live_input


def replay(source: Path, output: Path) -> dict:
    if output.exists() or not output.resolve().is_relative_to(REPO_ROOT / "runs"):
        raise ValueError("use a fresh directory under runs/")
    output.mkdir(parents=True)
    rows = json.loads((source / "attempts.json").read_text())
    report = []
    for row in rows:
        original = REPO_ROOT / "runs" / row["run_dir"]
        config = RunConfig.model_validate_json((original / "config.json").read_text())
        raw = config.model_dump(mode="json") | {"mode": "replay"}
        config = RunConfig.model_validate(raw)
        index = int(row["case"].split("-")[-1])
        inp = live_input(index, "s5-live-v2")
        inp.request["planning_mode"] = row["arm"]
        result = run_investigation(inp, config, ReplayProvider(original / "llm_trace.jsonl"), output,
            cache_dir=None, input_ref={"kind":"sprint5-live", "version":"s5-live-v2", "index":index},
            run_prefix=row["case"]+"-"+row["arm"]+"-replay-", reproduce="offline recorded-response replay")
        saved = json.loads((original / "investigation.json").read_text())
        if (result.result.reported_claims != tuple(saved["reported_claims"]) or result.result.follow_up != saved["follow_up"]
                or result.result.cost.actual_usd != 0 or result.result.status.value != row["status"]):
            raise ValueError("recorded response replay changed: "+row["case"]+"/"+row["arm"])
        scored = score(result.run_dir, inp.graph, False)
        if scored["errors"] or scored["unsupported"]:
            raise ValueError("replayed evidence failed independent checks")
        report.append({"case":row["case"],"arm":row["arm"],"claims_match":True,"follow_up_matches":True,
                       "status":result.outcome.status,"usd":0,"run_dir":result.run_dir.name})
    summary = {"replayed":len(report),"all_claims_and_decisions_match":True,"paid_spend_usd":0,"rows":report}
    write_json(output/"verification.json",summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(replay(Path(sys.argv[1]),Path(sys.argv[2])),indent=2))
