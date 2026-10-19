"""Frozen live evaluation current-system-eval-v2 (protocols/current_system_eval_v2.json).

All cases run in parallel as separate processes (starts staggered 1 s). One attempt per case.
`--mock` runs the same plumbing with scripted roles and a separate zero-cost ledger (plumbing check only;
never evaluation evidence). Live mode needs `--allow-paid` and enforces a USD 3.00 batch ceiling above
the spend already recorded in the main ledger.
"""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
import hashlib
import json
import subprocess
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
PROTOCOL = ROOT / "protocols" / "current_system_eval_v2.json"
PROTOCOL_SHA = "f64dffce934c256053866014d6f7deef75ca2c332df45df5ca05d2275f2087e0"
MOCK = "--mock" in sys.argv
OUT = ROOT / "runs" / ("current-system-eval-v2-mock" if MOCK else "current-system-eval-v2")
LEDGER = OUT / "ledger" if MOCK else ROOT / "runs"  # mock never touches the main ledger


def save(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def worker(case_id: str) -> None:
    started = time.perf_counter()
    from blackgrid.agent.roles import InvestigationInput
    from blackgrid.contracts import RunConfig
    from blackgrid.data.collegemsg import build_graph
    from blackgrid.workflow import runner

    case = next(c for c in json.loads((OUT / "questions.json").read_text(encoding="utf-8")) if c["id"] == case_id)
    cfg = json.loads((OUT / "base_config.json").read_text(encoding="utf-8"))
    cfg["question"] = case["question"]
    config = RunConfig.model_validate(cfg)
    runner.renderer = lambda rt, state: None  # presentation excluded; science, planning, critic and report unchanged
    try:
        built = build_graph(ROOT, config)
        inp = InvestigationInput(case_id=built.record.graph_id, question=case["question"],
                                 request={"method": "auto", "family": "auto", "planning_mode": config.planning_mode},
                                 graph=built.graph, record=built.record, spec=config.experiment)
        result = runner.run_investigation(inp, config, None, LEDGER, cache_dir=ROOT / "runs" / "cache",
                                          input_ref={"kind": "collegemsg", "data_root": str(ROOT)},
                                          run_prefix=f"evalv2-{case_id}-", allow_paid=not MOCK,
                                          reproduce=f"python scripts/evaluate_current_v2.py --worker {case_id}")
        save(OUT / f"{case_id}.json", {"id": case_id, "elapsed_s": time.perf_counter() - started,
                                       "run_dir": str(result.run_dir), "outcome": result.outcome.status})
    except Exception as exc:
        save(OUT / f"{case_id}.json", {"id": case_id, "elapsed_s": time.perf_counter() - started,
                                       "error": type(exc).__name__ + ": " + str(exc)[:500]})
        traceback.print_exc()


def recorded_spend() -> tuple[float, float]:
    """(project-wide, current-sprint) spend already counted by the caps, before this batch."""
    from blackgrid.workflow.api import open_services

    services = open_services(LEDGER)
    try:
        return services.store.spend_elsewhere("__evalv2_preflight__")
    finally:
        services.close()


def main() -> None:
    if not MOCK and "--allow-paid" not in sys.argv:
        sys.exit("live evaluation makes paid calls: add --allow-paid (authorized: USD 3.00 batch ceiling)")
    if hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() != PROTOCOL_SHA:
        sys.exit("frozen protocol changed after freezing; refusing to run")
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    ex = protocol["execution"]
    OUT.mkdir(parents=True, exist_ok=False)
    project, sprint = recorded_spend()
    cfg = json.loads((ROOT / "configs" / "collegemsg_live.json").read_text(encoding="utf-8"))
    cfg.update({"investigation_family": "auto", "planning_mode": ex["planning_mode"], "deadline_s": 540})
    if MOCK:
        cfg["mode"] = "mock"
        cfg["budget"] = {"max_usd_total": 0.0, "max_usd_current_sprint": 0.0, "max_usd_per_investigation": 0.0}
    else:
        cfg["budget"] = {"max_usd_total": round(project + ex["batch_ceiling_usd"], 6),
                         "max_usd_current_sprint": round(sprint + ex["batch_ceiling_usd"], 6),
                         "max_usd_per_investigation": ex["per_case_cap_usd"]}
        cfg["llm"]["model"] = ex["model"]
    save(OUT / "base_config.json", cfg)
    save(OUT / "questions.json", [{"id": c["id"], "question": c["question"]} for c in protocol["cases"]])
    save(OUT / "launch.json", {"protocol_sha256": PROTOCOL_SHA, "mode": "mock" if MOCK else "live",
                               "recorded_spend_before": {"project_usd": project, "current_sprint_usd": sprint},
                               "caps": cfg["budget"], "started_utc": datetime.now(UTC).isoformat(),
                               "source_hashes": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                                 for p in (ROOT / "src").rglob("*.py")}})
    start = time.perf_counter()
    procs = []
    for case in protocol["cases"]:
        log = (OUT / f"{case['id']}.log").open("w", encoding="utf-8")
        args = [sys.executable, __file__, "--worker", case["id"]] + (["--mock"] if MOCK else [])
        procs.append((case["id"], subprocess.Popen(args, cwd=ROOT, stdout=log, stderr=log), log, time.perf_counter()))
        time.sleep(1.0)  # staggered starts: all cases still run in parallel
    print(f"dispatched {len(procs)} cases ({'mock' if MOCK else 'live'}); per-case cap ${cfg['budget']['max_usd_per_investigation']}",
          flush=True)
    while any(p.poll() is None for _, p, _, _ in procs):
        if time.perf_counter() - start > ex["external_timeout_s"]:
            for cid, p, _, _ in procs:
                if p.poll() is None:
                    p.kill()
                    save(OUT / f"{cid}.json", {"id": cid, "error": "external_timeout",
                                               "elapsed_s": ex["external_timeout_s"]})
            break
        time.sleep(1)
    for _, p, log, _ in procs:
        p.wait()
        log.close()
    save(OUT / "execution.json", {"elapsed_s": time.perf_counter() - start,
                                  "exit_codes": {cid: p.returncode for cid, p, _, _ in procs},
                                  "finished_utc": datetime.now(UTC).isoformat()})
    print(f"finished in {time.perf_counter() - start:.0f} s -> {OUT}", flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--worker":
        worker(sys.argv[2])
    else:
        main()
