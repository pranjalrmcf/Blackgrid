"""Reconcile retained raw benchmark samples with the independent durable ledger."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path): return json.loads(path.read_bytes())


def quantiles(values):
    # Independent calculation from raw measurements, not imported benchmark code.
    values = sorted(values)
    assert all(math.isfinite(v) and v >= 0 for v in values)
    return {"samples":len(values), **{f"p{q}":values[math.ceil(len(values)*q/100)-1] if values else None for q in (50,95,99)}}


def reconcile(folder):
    attempt = load(folder/"attempt.json")
    protocol_bytes = (folder/"registered_protocol.json").read_bytes()
    protocol = json.loads(protocol_bytes)
    digest = hashlib.sha256(protocol_bytes).hexdigest()
    assert digest == attempt["protocol_sha256"]
    assert attempt["mode"] == "mock" and attempt["actual_usd"] == attempt["real_provider_calls"] == 0
    ledger = {r["id"]:r for r in load(folder/"job_ledger.json")}
    assert all(r["mode"] == "mock" and r["charged_usd"] == 0 for r in ledger.values())
    seen, stages = set(), []
    for spec in attempt["stages"]:
        stage = folder/spec["directory"]
        assert spec["exit_code"] == 0
        if spec["category"] == "tools":
            tools, mock = load(stage/"tools.json"), load(stage/"mock.json")
            assert len(tools["rows"]) == 30
            assert all(r["origin"] == "synthetic" and r["state"] == "completed" and r["nodes"] <= 1000 and r["edges"] <= 10000 for r in tools["rows"])
            assert len({r["case"] for r in tools["rows"]}) == 15
            assert mock["actual_usd"] == mock["real_provider_calls"] == 0 and mock["malformed_fixture_detected"]
            continue
        s = load(stage/"summary.json")
        samples, resources = load(stage/"http_samples.json"), load(stage/"resource_series.json")
        c = s["counts"]
        assert s["protocol_sha256"] == digest and s["state"] == "completed" and s["stop_reason"] is None
        assert s["configured_users"] == s["observed_peak_users"] == spec["users"]
        assert s["actual_usd"] == 0 and s["identity"]["live_enabled"] is False and s["identity"]["origin"] == "synthetic"
        assert len(samples) == c["requests"] <= protocol["max_http_samples"]
        assert s["api_latency_ms"] == quantiles([r["milliseconds"] for r in samples])
        for route, expected in s["route_latency_ms"].items():
            assert expected == quantiles([r["milliseconds"] for r in samples if r["route"] == route])
        assert c["rate_limited"] == sum(r["status"] == 429 for r in samples)
        assert c["rejected"] == sum(r["route"] == "job_submit" and r["status"] in (429,503) for r in samples)
        assert c["unexpected_errors"] == sum(r["status"] not in (200,202,429,503) for r in samples)
        assert c["accepted"] == len(s["jobs"]) == sum(r["route"] == "job_submit" and r["status"] == 202 for r in samples)
        assert s["offered_submissions"] == c["accepted"]+c["rejected"]
        assert c["completed"] == sum(j["state"] == "completed" and j["result_verified"] for j in s["jobs"].values())
        assert c["accepted"] == c["completed"]+c["failed"]+c["censored"]
        waits, terminal, worker = [], [], []
        for job_id, j in s["jobs"].items():
            assert job_id not in seen
            seen.add(job_id)
            durable = ledger[job_id]
            assert durable["state"] == j["state"] and durable["attempts"] == j["attempts"]
            assert durable["created"] == j["created_utc"] and durable["started"] == j["started_utc"] and durable["finished"] == j["completed_utc"]
            assert j["actual_usd"] == 0
            def elapsed(a,b): return (datetime.fromisoformat(b)-datetime.fromisoformat(a)).total_seconds()
            if durable["started"]: waits.append(elapsed(durable["created"],durable["started"]))
            if durable["finished"]: terminal.append(elapsed(durable["created"],durable["finished"]))
            if durable["started"] and durable["finished"]: worker.append(elapsed(durable["started"],durable["finished"]))
        assert s["queue_wait_seconds"] == quantiles(waits)
        assert s["creation_to_terminal_seconds"] == quantiles(terminal)
        assert s["agent_worker_seconds"] == quantiles(worker)
        assert all(r["users"] <= spec["users"] and r["elapsed_s"] <= s["elapsed_s"] for r in resources)
        stages.append(dict(category=spec["category"], users=spec["users"], requests=c["requests"],
            accepted=c["accepted"], completed=c["completed"], incomplete=c["failed"], rejected=c["rejected"],
            censored=c["censored"], unexpected_errors=c["unexpected_errors"],
            api_p95_ms=s["api_latency_ms"]["p95"], api_p99_ms=s["api_latency_ms"]["p99"],
            queue_p95_s=s["queue_wait_seconds"]["p95"], terminal_p95_s=s["creation_to_terminal_seconds"]["p95"],
            completed_per_minute=s["completed_analyses_per_minute"], elapsed_s=s["elapsed_s"],
            peak_memory_bytes=max(r["memory_bytes"] or 0 for r in resources),
            generator_cpu_seconds=s["generator_cpu_seconds"], generator_peak_rss_bytes=s["generator_peak_rss_bytes"]))
    assert set(ledger) == seen
    report = dict(attempt=folder.name, version=attempt["version"], reconciled=True,
        ledger_jobs=len(ledger), partial_jobs=sum(r["state"] == "partial" for r in ledger.values()),
        actual_usd=0, real_provider_calls=0, graph_samples=30, stages=stages, host=attempt["host"],
        source_revision=attempt["source_revision"], source_dirty=attempt["source_dirty"], image_id=attempt["target_image_id"])
    (folder/"reconciliation.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    with (folder/"stages.csv").open("w",newline="",encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(stages[0]))
        writer.writeheader(); writer.writerows(stages)
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt",type=Path)
    reconcile(parser.parse_args().attempt.resolve())
