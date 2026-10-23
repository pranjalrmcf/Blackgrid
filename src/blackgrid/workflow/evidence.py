"""Pinned operator evidence for isolated API workers; never model-selected paths."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import Field

from blackgrid.contracts import Contract

FILES = {
    "selection": "prediction/selection.json",
    "prediction_freeze": "prediction/freeze.json",
    "validation": "prediction/validation.json",
    "test_evaluation": "prediction/test_evaluation.json",
    "predictions_manifest": "prediction/predictions_manifest.json",
    "rolling": "rolling/summary.json",
    "confirmation": "confirmation/summary.json",
    "research": "research/sprint7_manifest.json",
}


class EvidenceFile(Contract):
    path: Path
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    def verified(self) -> Path:
        if (self.path.is_symlink() or not self.path.is_file() or self.path.stat().st_size > 16 * 1024**2
                or hashlib.sha256(self.path.read_bytes()).hexdigest() != self.sha256):
            raise ValueError("pinned tool evidence changed or unavailable")
        return self.path


class ToolEvidence(Contract):
    version: Literal["api-tools-v1"] = "api-tools-v1"
    research_profile: Literal["api-beliefs-portability-v1"] = "api-beliefs-portability-v1"
    files: dict[str, EvidenceFile] = Field(default_factory=dict)

    def file(self, name: str) -> Path | None:
        item = self.files.get(name)
        return item.verified() if item else None

    @classmethod
    def capture(cls, root: Path | None):
        files = {}
        if root is not None:
            root = root.resolve()
            for name, relative in FILES.items():
                path = root / relative
                if path.is_file():
                    if path.is_symlink() or not path.resolve().is_relative_to(root) or path.stat().st_size > 16 * 1024**2:
                        raise ValueError("unsafe tool evidence")
                    files[name] = EvidenceFile(path=path.resolve(), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        return cls(files=files)

    def forecast_ready(self):
        return all(name in self.files for name in ("selection", "prediction_freeze", "validation", "test_evaluation", "predictions_manifest"))


def read_binding(path: Path | None) -> dict | None:
    if path is None:
        return None
    if path.is_symlink() or path.stat().st_size > 32768:
        raise ValueError("invalid tool evidence binding")
    return ToolEvidence.model_validate_json(path.read_bytes()).model_dump(mode="json")
