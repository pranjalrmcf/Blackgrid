"""Full-file, aggregate-only CollegeMsg ingestion, separate from bounded experiments.

No inference or model calls occur here. Raw events and node identifiers stay in memory.
"""
from __future__ import annotations

import hashlib
import json
import platform
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import networkx as nx

from blackgrid.collegemsg import DataIntegrityError, graph_sha256, load_events, project
from blackgrid.contracts import DatasetSource


def ingest_full(root: Path, source: DatasetSource) -> dict:
    """Verify all rows and return reproducible, identifier-free descriptive statistics.

    Repeated events remain in event counts. The simple projection merges repeated pairs,
    discards direction and excludes self-loops, retaining all active nodes.
    """
    if source.rights_status.value != "accepted_local_noncommercial":
        raise DataIntegrityError("full ingestion requires the recorded local-use rights decision")
    base = root.resolve()
    path = (base / source.path).resolve()
    if not path.is_relative_to(base):
        raise DataIntegrityError("dataset path escapes data root")
    table = load_events(path, source.sha256)
    if table.malformed_rows:
        raise DataIntegrityError(f"full ingestion refused: {table.malformed_rows} malformed rows")
    if not table.events:
        raise DataIntegrityError("full ingestion refused: no valid events")
    graph = project(table.events)
    directed = nx.DiGraph()
    directed.add_nodes_from(graph)
    directed.add_edges_from((u, v) for u, v, _ in table.events if u != v)
    components = sorted((len(c) for c in nx.connected_components(graph)), reverse=True)
    degrees = sorted(d for _, d in graph.degree())
    middle = len(degrees) // 2
    median = (degrees[middle] if len(degrees) % 2 else
              (degrees[middle - 1] + degrees[middle]) / 2)
    start = min(t for _, _, t in table.events)
    stop = max(t for _, _, t in table.events)
    # Fixed seven-day bins anchored to the first timestamp; include empty weeks.
    bins = defaultdict(list)
    for event in table.events:
        bins[(event[2] - start) // 604800].append(event)
    weeks = []
    for index in range((stop - start) // 604800 + 1):
        events = bins[index]
        weeks.append({"index": index, "start_timestamp": start + index * 604800,
                      "end_timestamp_exclusive": start + (index + 1) * 604800,
                      "events": len(events),
                      "active_nodes": len({n for u, v, _ in events for n in (u, v)})})
    return {
        "schema_version": "full-collegemsg-ingestion-v1",
        "scope": "full_file_descriptive_only", "status": "completed",
        "source": {"dataset_id": source.dataset_id, "sha256": source.sha256,
                   "source_url": source.source_url, "citations": list(source.citations),
                   "rights_status": source.rights_status.value,
                   "rights_decision": source.rights_decision,
                   "raw_redistribution_performed": False},
        "validation": table.summary(),
        "time": {"first_utc": datetime.fromtimestamp(start, UTC).isoformat(),
                 "last_utc": datetime.fromtimestamp(stop, UTC).isoformat(),
                 "span_seconds": stop - start, "weekly_bins": weeks},
        "projection": {"kind": "simple_undirected_unweighted",
                       "sha256": graph_sha256(graph), "nodes": len(graph),
                       "edges": graph.number_of_edges(), "density": nx.density(graph),
                       "components": len(components), "component_sizes": components,
                       "largest_component_nodes": components[0],
                       "isolated_nodes": nx.number_of_isolates(graph),
                       "mean_degree": sum(degrees) / len(degrees),
                       "median_degree": median, "max_degree": max(degrees),
                       "triangles": sum(nx.triangles(graph).values()) // 3,
                       "transitivity": nx.transitivity(graph),
                       "strong_components_in_directed_projection":
                           nx.number_strongly_connected_components(directed)},
        "environment": {"python": platform.python_version(), "networkx": nx.__version__},
        "execution": {"llm_calls": 0, "paid_cost_usd": 0, "network_calls": 0},
        "limitations": [
            "Description of observed messages; absent pairs are unknown, not known non-links.",
            "No causal conclusions, community significance test, or full-network agent run.",
            "Repeated events retained; projection discards direction, frequency and time.",
            "Historical seven-day experiment and its resource limits remain unchanged.",
            "Local-use decision does not establish a redistribution license."
        ]
    }


def write_ingestion(report: dict, output: Path) -> Path:
    """Create a fresh report directory; never overwrite a previous ingestion."""
    output.mkdir(parents=True, exist_ok=False)
    payload = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    (output / "ingestion.json").write_bytes(payload)
    checksum = hashlib.sha256(payload).hexdigest()
    (output / "ingestion.sha256").write_text(checksum + "\n", encoding="ascii")
    counts, graph = report["validation"], report["projection"]
    (output / "README.md").write_text(
        "# Full CollegeMsg ingestion\n\n"
        f"Validated {counts['valid_events']:,} events across {graph['nodes']:,} people "
        f"and {graph['edges']:,} distinct undirected connections.\n\n"
        f"Exact duplicate rows: {counts['exact_duplicate_rows']:,}; retained and flagged. "
        f"Malformed rows: {counts['malformed_rows']}.\n\n"
        "All records were read. Only aggregate statistics and hashes were saved. "
        "This prepares the data for future research; it does not test whether groups "
        "are unusual or establish why people communicate.\n\n"
        "The previous seven-day experiment is unchanged. No LLM calls or paid services "
        "were used. See ingestion.json for the source, versions, counts and limitations.\n",
        encoding="utf-8")
    return output
