"""Schema-driven temporal edge-list loader for datasets beyond CollegeMsg (Sprint 6 extension, D-077).

Each dataset declares its separator, header, source/target/time columns, timestamp format, ID type
and optional attribute columns. The checksum is verified first; malformed rows are counted by reason,
never repaired. String or large IDs are mapped to dense integers in first-seen order (deterministic
for a fixed file). Only aggregate profiles leave this module. Unauthorized datasets cannot be loaded.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field

from blackgrid.contracts import Contract

Event = tuple[int, int, int]


class DatasetSchema(Contract):
    dataset_id: str
    path: str  # relative to the data root
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    separator: str | None = None  # None = any whitespace
    header: bool = False
    source_col: int = 0
    target_col: int = 1
    time_col: int = 2
    time_format: Literal["unix", "datetime"] = "unix"  # datetime = "%Y-%m-%d %H:%M:%S" (UTC)
    attribute_cols: dict[str, int] = {}  # e.g. {"rating": 2}; numeric attributes only
    rights_decision: str
    rights_status: Literal["accepted_local_noncommercial"]
    citations: tuple[str, ...] = Field(min_length=1)
    source_url: str
    semantics: str  # what an edge means, used in reports


BITCOIN_OTC = DatasetSchema(
    dataset_id="snap-bitcoin-otc", path="soc-sign-bitcoinotc.csv/soc-sign-bitcoinotc.csv",
    sha256="76bd9d8f1d3ff9a1813d9fc8e6902a0ee4d0a2f8c1003842dbc9ec79149ab60c", separator=",", time_col=3,
    attribute_cols={"rating": 2}, rights_decision="D-077", rights_status="accepted_local_noncommercial",
    citations=("Kumar, Spezzano, Subrahmanian, Faloutsos. Edge Weight Prediction in Weighted Signed Networks. ICDM 2016.",
               "Kumar, Hooi, Makhija, Kumar, Faloutsos, Subrahmanian. REV2: Fraudulent User Prediction in Rating "
               "Platforms. WSDM 2018."),
    source_url="https://snap.stanford.edu/data/soc-sign-bitcoin-otc.html",
    semantics="a trust rating (-10..+10) given by one user to another")

REGISTRY = {s.dataset_id: s for s in (BITCOIN_OTC,)}  # only user-authorized datasets are registered


class DatasetError(RuntimeError):
    pass


@dataclass
class LoadedDataset:
    schema: DatasetSchema
    events: list[Event]
    attributes: dict[str, list[float]]  # aligned with events
    sha256: str
    profile: dict = field(default_factory=dict)  # aggregates only


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _time(token: str, fmt: str) -> int:
    if fmt == "unix":
        return int(float(token))
    return int(datetime.strptime(token[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp())


def load(dataset_id: str, data_root: Path) -> LoadedDataset:
    if dataset_id not in REGISTRY:
        raise DatasetError(f"dataset {dataset_id!r} is not registered (no recorded rights decision)")
    schema = REGISTRY[dataset_id]
    path = data_root / schema.path
    if not path.is_file():
        raise DatasetError(f"input file not found: {schema.path}")
    actual = _sha256(path)
    if actual != schema.sha256:
        raise DatasetError(f"checksum mismatch for {dataset_id}: expected {schema.sha256}, got {actual}")
    ids: dict[str, int] = {}
    events: list[Event] = []
    attrs: dict[str, list[float]] = {name: [] for name in schema.attribute_cols}
    malformed: Counter = Counter()
    need = max(schema.source_col, schema.target_col, schema.time_col, *schema.attribute_cols.values(), 0) + 1
    seen_rows: set = set()
    duplicates = self_loops = 0
    with path.open("r", encoding="utf-8", errors="strict") as fh:
        if schema.header:
            next(fh, None)
        for line in fh:
            line = line.rstrip("\r\n")
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split(schema.separator) if schema.separator else line.split()
            if len(parts) < need:
                malformed["too_few_fields"] += 1
                continue
            try:
                t = _time(parts[schema.time_col].strip(), schema.time_format)
                values = {name: float(parts[col]) for name, col in schema.attribute_cols.items()}
            except ValueError:
                malformed["unparseable_time_or_attribute"] += 1
                continue
            src, dst = parts[schema.source_col].strip(), parts[schema.target_col].strip()
            if not src or not dst:
                malformed["empty_id"] += 1
                continue
            u = ids.setdefault(src, len(ids))
            v = ids.setdefault(dst, len(ids))
            key = (u, v, t)
            duplicates += key in seen_rows
            seen_rows.add(key)
            self_loops += u == v
            events.append((u, v, t))
            for name, value in values.items():
                attrs[name].append(value)
    times = [t for _, _, t in events]
    profile = {"dataset_id": dataset_id, "sha256": actual, "valid_events": len(events),
               "malformed_by_reason": dict(malformed), "nodes": len(ids), "self_loop_events": self_loops,
               "exact_duplicate_rows": duplicates, "min_timestamp": min(times) if times else None,
               "max_timestamp": max(times) if times else None, "semantics": schema.semantics,
               "rights_decision": schema.rights_decision}
    for name, values in attrs.items():
        profile[f"{name}_positive_fraction"] = sum(v > 0 for v in values) / len(values) if values else None
    return LoadedDataset(schema=schema, events=events, attributes=attrs, sha256=actual, profile=profile)
