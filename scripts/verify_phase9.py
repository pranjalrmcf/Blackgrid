"""Synthetic staging, schema compatibility and observability smoke; no private inputs."""

import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from fastapi.testclient import TestClient

from blackgrid.operations.api import create_app
from blackgrid.operations.api_jobs import Jobs
from blackgrid.operations.settings import Settings
from scripts.generate_phase6 import generate
from scripts.verify_phase7 import main as restore_drill
from tests.test_api import headers
from tests.test_monitoring import OPS


def main():
    assert os.name == "posix" and Path("/evidence").is_dir()
    restore_drill()
    root = Path("/tmp/phase9-staging")
    generate(root / "input", sizes=(100,))
    state = root / "state"
    (state / "cache").mkdir(parents=True)
    settings = Settings(
        environment="test",
        config=root / "input/public/stochastic_block-100.json",
        data_root=root / "input/public",
        runs_dir=state,
        api_tool_cache=True,
    )
    with TestClient(create_app(settings, OPS), base_url="http://127.0.0.1") as client:
        assert client.get("/health/ready").status_code == 200
        assert client.get("/api/v1/capabilities", headers=headers()).status_code == 200
        snapshot = client.get("/api/v1/monitoring.json", headers=headers()).json()
        assert snapshot["scheduler_available"] and snapshot["database_available"]
        assert isinstance(snapshot["alerts"], list)
        assert (
            client.get("/api/v1/monitoring.json", headers=headers("bob")).status_code
            == 403
        )
        with closing(client.app.state.jobs.db()) as db:
            before = db.execute(
                "select sql from sqlite_master order by name"
            ).fetchall()
    reopened = Jobs(settings)
    try:
        with closing(reopened.db()) as db:
            assert db.execute("pragma integrity_check").fetchone()[0] == "ok"
            assert (
                before
                == db.execute("select sql from sqlite_master order by name").fetchall()
            )
    finally:
        reopened.close()
    report = dict(
        version="production-phase9-v1",
        origin="synthetic",
        mode="mock",
        monitoring=True,
        alerts=True,
        schema_reopen_exact=True,
        real_provider_calls=0,
        actual_usd=0,
        production_state_touched=False,
    )
    Path("/evidence/staging.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
