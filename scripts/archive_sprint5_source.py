"""Create a verified local source snapshot for Sprint 5 clean reproduction."""
import hashlib
import json
import shutil
import sys
from pathlib import Path


def archive(run: Path, target: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    target = target.resolve()
    if target.exists() or not target.is_relative_to(root / "runs"):
        raise ValueError("snapshot must be a fresh directory under local runs/")
    receipt = json.loads((run / "freeze.json").read_text())
    files = dict(receipt["source_hashes"])
    for name in ("README.md", "AGENTS.md", "PROJECT_CONTEXT.md", "SPRINT_01.md", "SPRINT_05.md"):
        files[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    for path in (root / "configs").glob("*.json"):
        files[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name, expected in files.items():
        source = (root / name).resolve()
        if not source.is_relative_to(root) or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError("source changed since freeze: " + name)
    target.mkdir(parents=True)
    for name in files:
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / name, destination)
    (target / "snapshot.json").write_text(json.dumps({"files": files,
        "note": "Local source/config snapshot only. No credentials, raw data, node rankings or historical run artifacts copied."}, indent=2))
    print(json.dumps({"files": len(files), "snapshot": str(target)}))


if __name__ == "__main__":
    archive(Path(sys.argv[1]), Path(sys.argv[2]))
