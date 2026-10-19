"""Archive exactly the frozen source for reproduction, without raw data/secrets/runs."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def archive(run: Path, target: Path, root: Path) -> dict:
    receipt = json.loads((run / "freeze.json").read_text(encoding="utf-8"))
    root, target = root.resolve(), target.resolve()
    assert target.is_relative_to(root / "runs"), "snapshot must remain in ignored local runs/"
    assert not target.exists(), "never overwrite a snapshot"
    files = {}
    for name, expected in receipt["source_hashes"].items():
        path = (root / name).resolve()
        assert path.is_relative_to(root)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name
        files[name] = path
    for name in ("README.md", "AGENTS.md", "PROJECT_CONTEXT.md", "sprints/SPRINT_01.md", "sprints/SPRINT_02.md", "sprints/SPRINT_03.md"):
        files[name] = root / name
    # Runtime rendering needs the HTML template too, not just Python modules.
    # These inherited assets were unchanged during the scientific execution;
    # verify them against its recorded Git revision before including them.
    for path in (root / "src/blackgrid").rglob("*"):
        if path.suffix not in (".html", ".css", ".js"):
            continue
        name = path.relative_to(root).as_posix()
        expected = subprocess.check_output(["git", "-C", str(root), "show",
                                            receipt["environment"]["source_commit"] + ":" + name])
        assert path.read_bytes() == expected, "unfrozen runtime asset: " + name
        files[name] = path
    target.mkdir(parents=True)
    for name, path in files.items():
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    manifest = {"source_run": str(run.resolve()), "files": {
        name: hashlib.sha256((target / name).read_bytes()).hexdigest() for name in files},
        "note": "Local source snapshot only; no raw data, secrets, old results or evaluator mappings copied."}
    (target / "snapshot.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"snapshot": str(target), "files": len(files)}


if __name__ == "__main__":
    print(json.dumps(archive(Path(sys.argv[1]), Path(sys.argv[2]), Path(__file__).resolve().parents[1])))
