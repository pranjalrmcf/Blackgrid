"""Actual trusted graph tools and isolated mock scenarios; no real provider."""
import hashlib
import json
import time
from pathlib import Path
from blackgrid.agent.providers import MockProvider, ProviderError
from blackgrid.agent.tools import ToolContext, execute
from blackgrid.contracts import RunConfig
from blackgrid.data.collegemsg import build_graph
from blackgrid.operations.benchmark_mock import LatencyMockProvider
from benchmarks.production.common import atomic_json, quantiles


def graph_bench(root, output):
    rows = []
    for config_path in sorted(root.glob("*.json")):
        if config_path.name.endswith(".manifest.json"):
            continue
        config = RunConfig.model_validate_json(config_path.read_bytes())
        start = time.perf_counter()
        built = build_graph(root, config)
        ctx = ToolContext(built.graph, built.record, config.experiment)
        for tool in ("profile_graph", "node_centrality"):
            before = time.perf_counter()
            try:
                execute({"tool": tool, "args": {}}, ctx)
                state = "completed"
            except Exception:
                state = "failed"
            rows.append(dict(case=config_path.stem, tool=tool, seconds=time.perf_counter()-before,
                origin=built.record.origin.value, nodes=len(built.graph), edges=built.graph.number_of_edges(),
                state=state, data_sha256=config.dataset.sha256, generator_sha256=built.record.generator_sha256))
        if time.perf_counter()-start > 60:
            break
    atomic_json(output/"tools.json", {"category": "graph_computation", "rows": rows,
        "claim": "engineering timings only; not synthetic efficacy or real-world validity", "actual_usd": 0})
    return rows


def mock_bench(output):
    results = []
    # Aggregate-only synthetic prompts of explicit differing sizes. No data IDs/truth.
    for size, fixture_latency in zip((128, 1024, 4096), (.025, .075, .15)):
        provider = MockProvider()
        payload = {"task": {"question": "Which nodes have highest degree?", "request": {"family": "centrality"}}}
        messages = [{"role": "user", "content": "aggregate_fixture "*(size//18)}]
        start = time.perf_counter()
        time.sleep(fixture_latency)
        completion = provider.complete("planner", payload, messages, 1000)
        results.append(dict(scenario="latency", prompt_bytes=len(messages[0]["content"]),
            seconds=time.perf_counter()-start, input_tokens=completion.prompt_tokens,
            output_tokens=completion.completion_tokens, valid_json=isinstance(json.loads(completion.text), dict)))
    # Known fake error classes. This harness does not call the network or claim agent recovery.
    for category in ("transient", "permanent", "uncertain"):
        start = time.perf_counter()
        try:
            raise ProviderError("synthetic benchmark failure", category)
        except ProviderError as exc:
            results.append(dict(scenario="error_fixture", category=exc.category, seconds=time.perf_counter()-start))
    bad = MockProvider(script={"planner": ["{"]}).complete("planner", {}, [], 100)
    try:
        json.loads(bad.text)
        malformed = False
    except ValueError:
        malformed = True
    atomic_json(output/"mock.json", dict(category="offline_mock_execution", actual_usd=0, real_provider_calls=0,
        malformed_fixture_detected=malformed, rows=results, latency=quantiles([r["seconds"] for r in results if r["scenario"] == "latency"]),
        limitations="Scripted latency/errors; does not measure real inference, quality, streaming TTFT or production provider reliability."))
