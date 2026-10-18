"""Minimized local live-run summary: no prompts, node rows or credentials exported."""
import hashlib
import json
import sys
from pathlib import Path

from blackgrid.live_allowance import read_allowance
from blackgrid.runner import REPO_ROOT, write_json


def audit(folder: Path) -> dict:
    manifest = json.loads((folder / "manifest.json").read_text())
    for name, expected in manifest["artifacts"].items():
        path = (folder / name).resolve()
        if not path.is_relative_to(folder.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("artifact integrity failed")
    trace = [json.loads(line) for line in (folder / "llm_trace.jsonl").read_text().splitlines() if line]
    return {"artifacts_verified":len(manifest["artifacts"]),
            "provider_reported_usd":sum(x["reported_usd"] for x in trace) if trace and all(x.get("reported_usd") is not None for x in trace) else None,
            "truncations":sum(x.get("finish_reason")=="length" for x in trace)}


if __name__ == "__main__":
    runs=REPO_ROOT/"runs"
    output={"model":"deepseek/deepseek-v4-flash-0731","pilots":{},"allowance":read_allowance(runs/"sprint5-live-allowance.json",runs)}
    provider_total=0
    for name in ("sprint5-live-v1","sprint5-live-v2"):
        summary=json.loads((runs/name/"summary.json").read_text())
        attempts=json.loads((runs/name/"attempts.json").read_text())
        checks=[]
        for row in attempts:
            folder=(runs/row["run_dir"]).resolve()
            if not folder.is_relative_to(runs.resolve()): raise ValueError("run path outside local runs")
            checks.append(audit(folder))
        cost=sum(check["provider_reported_usd"] for check in checks) if all(check["provider_reported_usd"] is not None for check in checks) else None
        output["pilots"][name]={"protocol":summary["protocol"],"status":summary["status"],"arms":summary["arms"],
            "attempts":len(attempts),"provider_reported_usd":cost,"truncated_calls":sum(c["truncations"] for c in checks),
            "manifest_artifacts_verified":sum(c["artifacts_verified"] for c in checks)}
        if cost is not None: provider_total+=cost
    if len(sys.argv)!=2:
        raise ValueError("usage: export_sprint5_live_summary.py CONSOLE_RUN_ID")
    console=(runs/sys.argv[1]).resolve()
    if not console.is_relative_to(runs.resolve()): raise ValueError("console run outside local runs")
    inv=json.loads((console/"investigation.json").read_text())
    check=audit(console)
    output["console_smoke"]={"run_id":console.name,"status":inv["status"],"family":inv["family"],"mode":inv["cost"]["mode"],
        "llm_calls":inv["cost"]["llm_calls"],"claims":len(inv["reported_claims"]),"accounted_usd":inv["cost"]["actual_usd"],**check}
    provider_total+=check["provider_reported_usd"] or 0
    output["provider_reported_task_usd"]=provider_total
    replay=json.loads((runs/"sprint5-live-v2-replay"/"verification.json").read_text())
    output["replay"]={"runs":replay["replayed"],"claims_and_follow_up_match":replay["all_claims_and_decisions_match"],"paid_spend_usd":replay["paid_spend_usd"],
        "evidence":"runs/sprint5-live-v2-replay/verification.json"}
    output["limitations"]="Small exploratory pilots after development; structured claims only; not independent human validation or proof of adaptive benefit."
    destination=REPO_ROOT/"results"/"sprint05-live"
    destination.mkdir(exist_ok=True)
    write_json(destination/"summary.json",output)
    print(json.dumps({"accounted_task_usd":output["allowance"]["spent_usd"],"remaining_usd":output["allowance"]["remaining_usd"],
                      "provider_reported_task_usd":provider_total,"live_runs":13,"all_manifests_verified":True}))
