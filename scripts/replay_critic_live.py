"""Replay the current critic on the reviewed live-pilot claims (offline, free; development evidence only).

`uv run --frozen python scripts/replay_critic_live.py` -> results/sprint04-sprint4-live-v1/critic_replay.json
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from blackgrid.agent import flatten
from blackgrid.critic import CRITIC_VERSION, CriticContext, critique

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs" / "sprint4-live-v1"
OUT = ROOT / "results" / "sprint04-sprint4-live-v1" / "critic_replay.json"
ARTIFACTS = ("experiment_report.json", "sensitivity.json", "graph_profile.json")


def main() -> None:
    review = {r["review_id"]: r for r in csv.DictReader((RUN / "blinded_claims.csv").open(encoding="utf-8-sig"))}
    mapping = json.loads((RUN / "evaluator_private/blind_mapping.json").read_text(encoding="utf-8"))
    folders = {(p["case"], p["arm"]): Path(p["path"]) for p in json.loads((RUN / "agent_runs.json").read_text("utf-8"))
               if p.get("path")}
    rows = []
    for item in mapping:
        folder = folders[(item["case"], item["arm"])]
        outputs = {n: json.loads((folder / n).read_text("utf-8")) for n in ARTIFACTS if (folder / n).is_file()}
        report = outputs["experiment_report.json"]
        ctx = CriticContext(evidence=flatten(outputs), verdict=report["verdict"], delta_q=report["primary"].get("delta_q"),
                            p_value=report["primary"]["result"].get("p_value"), alpha=0.05)
        decision = critique(item["claim"], ctx)
        r = review[item["review_id"]]
        rows.append({"review_id": item["review_id"], "claim": item["claim"]["text"],
                     "review_accepts": r["support"] == "supported" and r["misleading"] == "no",
                     "critic_accepts": decision.accepted, "reasons": list(decision.reasons)})
    agree = Counter((r["review_accepts"], r["critic_accepts"]) for r in rows)
    summary = {"critic_version": CRITIC_VERSION, "claims": len(rows),
               "status": "development evidence: critic written after inspecting these claims; AI reviewer",
               "both_accept": agree[(True, True)], "both_reject": agree[(False, False)],
               "critic_rejects_review_accepts": agree[(True, False)],
               "critic_accepts_review_rejects": agree[(False, True)]}
    OUT.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    for r in rows:
        if r["review_accepts"] != r["critic_accepts"]:
            print("-", r["review_id"], "review", r["review_accepts"], "critic", r["critic_accepts"], "|", r["claim"][:110],
                  r["reasons"][:1])


if __name__ == "__main__":
    main()
