"""Explicit synthetic event provenance; default public-data loading is unchanged."""
from __future__ import annotations
import hashlib
import json
from dataclasses import replace
from blackgrid.contracts import DataOrigin, GraphRecord

PREFIX = "blackgrid-synthetic-v1:"


def mark_synthetic(built, root, config):
    if not config.dataset.source_url.startswith(PREFIX):
        return built
    from blackgrid.data.collegemsg import BoundedGraph
    if not isinstance(built, BoundedGraph) or config.scope != "first_window":
        raise ValueError("synthetic benchmark requires a bounded selected graph")
    path = root / config.dataset.path
    manifest_path = path.with_suffix(".manifest.json")
    if path.is_symlink() or manifest_path.is_symlink() or manifest_path.stat().st_size > 65536:
        raise ValueError("unsafe synthetic manifest")
    raw = manifest_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    manifest = json.loads(raw)
    if (config.dataset.source_url != PREFIX+digest or manifest.get("version") != "production-phase6-v1"
            or manifest.get("data_sha256") != config.dataset.sha256
            or manifest.get("projection_sha256") != built.record.projection_sha256
            or manifest.get("origin") != "synthetic" or manifest.get("rights") != "independently_generated_local"
            or not config.dataset.dataset_id.startswith("blackgrid-synthetic-")):
        raise ValueError("synthetic provenance mismatch")
    record = GraphRecord.model_validate(built.record.model_dump() | dict(origin=DataOrigin.SYNTHETIC,
        source=None, generator_sha256=digest, graph_id=config.dataset.dataset_id))
    return replace(built, record=record)
