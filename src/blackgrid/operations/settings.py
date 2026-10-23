"""Explicit deployment environment; unrelated variables and credentials are ignored."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Mapping

from pydantic import Field

from blackgrid.contracts import Contract

ROOT = Path(__file__).resolve().parents[3]


class Settings(Contract):
    environment: Literal["development", "test", "production"] = "production"
    config: Path = ROOT / "configs" / "collegemsg_sprint01.json"
    data_root: Path = ROOT
    runs_dir: Path = ROOT / "runs"
    evidence_root: Path | None = None
    benchmark_results_dir: Path | None = None
    benchmark_mock_profile: Literal["none", "latency"] = "none"
    api_tool_cache: bool = False
    port: int = Field(default=8765, ge=1, le=65535)
    shutdown_grace_seconds: float = Field(default=30, gt=0, le=300, allow_inf_nan=False)
    capabilities: tuple[Literal["community", "forecast", "research"], ...] = ("community",)

    @property
    def cache_dir(self) -> Path:
        return self.runs_dir / "cache"


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env
    names = {"environment": "ENV", "config": "CONFIG", "data_root": "DATA_ROOT",
             "runs_dir": "RUNS_DIR", "evidence_root": "EVIDENCE_ROOT", "benchmark_results_dir": "BENCHMARK_RESULTS_DIR",
             "benchmark_mock_profile": "BENCHMARK_MOCK_PROFILE", "api_tool_cache": "API_TOOL_CACHE",
             "port": "PORT", "shutdown_grace_seconds": "SHUTDOWN_GRACE_SECONDS"}
    values = {field: env["BLACKGRID_" + suffix] for field, suffix in names.items()
              if "BLACKGRID_" + suffix in env}
    if "BLACKGRID_CAPABILITIES" in env:
        values["capabilities"] = tuple(x.strip() for x in env["BLACKGRID_CAPABILITIES"].split(","))
    return Settings.model_validate(values)
