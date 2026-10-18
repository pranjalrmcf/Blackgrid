"""Verify saved Sprint 5 scores and optional clean reproduction without executing agents."""
import json
import sys
from pathlib import Path

from blackgrid.sprint5 import evaluation_input, score


def verify(folder: Path) -> dict:
    rows = json.loads((folder / "attempts.json").read_text())
    if len(rows) != 48 or len({(r["case"], r["arm"]) for r in rows}) != 48:
        raise ValueError("missing or duplicate attempts")
    for row in rows:
        index = int(row["case"].split("-")[-1])
        fresh = score(folder / row["run_dir"], evaluation_input(index).graph, index > 12)
        if any(row.get(key) != value for key, value in fresh.items()):
            raise ValueError("saved scores changed: " + row["run_dir"])
    return json.loads((folder / "summary.json").read_text())["arms"]


if __name__ == "__main__":
    arms = verify(Path(sys.argv[1]))
    if len(sys.argv) > 2 and verify(Path(sys.argv[2])) != arms:
        raise ValueError("clean reproduction differs")
    print(json.dumps({"attempts_verified": 48, "scores_and_hashes_verified": True,
                      "reproduction_matches": len(sys.argv) > 2}))
