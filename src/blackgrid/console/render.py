"""Render the console template, live or as a static snapshot with the data embedded."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path

from blackgrid.console.data import index_payload, pilot_payload, run_payload


def template() -> str:
    return resources.files("blackgrid.console").joinpath("template.html").read_text(encoding="utf-8")


def embed(boot: dict) -> str:
    """JSON safe inside <script type="application/json">: no '<', '>' or '&' can close the tag."""
    text = json.dumps(boot, ensure_ascii=True, sort_keys=True, default=str)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def page(boot: dict) -> str:
    return template().replace("__BOOT__", embed(boot), 1)


def live_page(token: str) -> str:
    return page({"mode": "live", "token": token})


def snapshot(view: str, payload: dict, base: str) -> str:
    """A static page: the same console, frozen with this run's data. `base` leads back to the runs root."""
    return page({"mode": "static", "view": view, "payload": payload, "base": base,
                 "generated": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")})


def _base(runs_dir: Path, folder: Path) -> str:
    depth = len(folder.resolve().relative_to(runs_dir.resolve()).parts)
    return "../" * depth


def write_run_snapshot(runs_dir: Path, run_dir: Path) -> Path:
    out = run_dir / "report.html"
    out.write_bytes(snapshot("run", run_payload(runs_dir, run_dir), _base(runs_dir, run_dir)).encode("utf-8"))
    return out


def write_pilot_snapshot(runs_dir: Path, pilot_dir: Path) -> Path:
    out = pilot_dir / "pilot.html"
    out.write_bytes(snapshot("pilot", pilot_payload(runs_dir, pilot_dir), _base(runs_dir, pilot_dir)).encode("utf-8"))
    return out


def write_index_snapshot(runs_dir: Path) -> Path:
    out = runs_dir / "index.html"
    out.write_bytes(snapshot("index", index_payload(runs_dir), "").encode("utf-8"))
    return out
