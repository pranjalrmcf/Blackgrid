"""Compare the Sprint 4 review sheet with the Sprint 3 evaluator and critic-v3 (development evidence only).

Run after the review sheet is complete: `uv run --frozen python scripts/compare_sprint4_review.py`.
Unblinds through runs/sprint3-v1.1/evaluator_private/blind_mapping.json, so never run it before review.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from blackgrid.agent import flatten
from blackgrid.critic import CRITIC_VERSION, CriticContext, critique

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "runs" / "sprint3-v1.1"
SHEET = ROOT / "results" / "sprint04-review" / "review_sheet.csv"
OUT = ROOT / "results" / "sprint04-review" / "comparison.json"
ARTIFACTS = ("experiment_report.json", "sensitivity.json", "graph_profile.json")


def main() -> None:
    mapping = {m["review_id"]: m for m in json.loads((SUITE / "evaluator_private/blind_mapping.json").read_text("utf-8"))}
    paths = {(r["case"], r["condition"]): SUITE / r["path"].replace("\\", "/")
             for r in json.loads((SUITE / "agent_runs.json").read_text("utf-8"))}
    rows = []
    for review in csv.DictReader(SHEET.open(encoding="utf-8-sig")):
        m = mapping[review["review_id"]]
        folder = paths[(m["case"], m["condition"])]
        outputs = {n: json.loads((folder / n).read_text("utf-8")) for n in ARTIFACTS if (folder / n).is_file()}
        report = outputs["experiment_report.json"]
        ctx = CriticContext(evidence=flatten(outputs), verdict=report["verdict"], delta_q=report["primary"].get("delta_q"),
                            p_value=report["primary"]["result"].get("p_value"), alpha=0.05)
        v3 = critique(m["claim"], ctx)
        rows.append({"review_id": review["review_id"], "condition": m["condition"], "claim": m["claim"]["text"],
                     "reviewer": review["reviewer"], "review_support": review["support"],
                     "review_accepts": review["support"] == "supported" and review["misleading"] == "no",
                     "sprint3_evaluator": m["assessment"][0], "critic_v3_accepts": v3.accepted,
                     "critic_v3_reasons": list(v3.reasons)})
    agree = Counter((r["review_accepts"], r["critic_v3_accepts"]) for r in rows)
    ev = Counter((r["review_accepts"], r["sprint3_evaluator"] == "supported") for r in rows)
    summary = {
        "status": "development evidence only: reviewer is an AI, critic-v3 was written knowing these claim forms",
        "critic_version": CRITIC_VERSION, "reviewers": dict(Counter(r["reviewer"] for r in rows)), "claims": len(rows),
        "sheet_sha256": hashlib.sha256(SHEET.read_bytes()).hexdigest(),
        "review_vs_critic_v3": {"both_accept": agree[(True, True)], "both_reject": agree[(False, False)],
                                "review_accepts_critic_rejects": agree[(True, False)],
                                "review_rejects_critic_accepts": agree[(False, True)]},
        "review_vs_sprint3_evaluator": {"both_accept": ev[(True, True)], "both_reject": ev[(False, False)],
                                        "review_accepts_evaluator_rejects": ev[(True, False)],
                                        "review_rejects_evaluator_accepts": ev[(False, True)]},
        "disagreements_with_critic_v3": [r for r in rows if r["review_accepts"] != r["critic_v3_accepts"]],
    }
    OUT.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "disagreements_with_critic_v3"}, indent=2))
    for r in summary["disagreements_with_critic_v3"]:
        print("-", r["review_id"], r["review_support"], "| v3", r["critic_v3_accepts"], "|", r["claim"][:80],
              r["critic_v3_reasons"][:1])


if __name__ == "__main__":
    main()
