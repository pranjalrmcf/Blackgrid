# Blackgrid

Bounded, evidence-grounded network-science investigations. Sprint 1 delivers one offline, reproducible vertical slice. It runs a preregistered community-vs-null experiment on a bounded CollegeMsg window, plus synthetic known-truth checks. The work is driven by a constrained planner/analyst, an allowlisted tool executor, and a rule-based critic. It produces an evidence-linked report or abstains.

Start with `PROJECT_CONTEXT.md`, `SPRINT_01.md`, and `AGENTS.md`. The study rules are in `protocols/sprint01_protocol.md` and `protocols/sprint01_experiment.md`. Every decision is in `docs/decision_log.md`, and the sprint outcome is in `docs/sprint01_report.md`.

## Status

Sprint 1 is implemented (Days 1–14). The mock pipeline is reproduced from a clean environment. **No live LLM run has been made yet.** See `docs/sprint01_report.md` for acceptance criteria, results, and limitations.

## 1. Setup (once)

You need Python 3.11 and [uv](https://docs.astral.sh/uv/). From the repository root:

```bash
uv sync --frozen
```

The raw dataset is not redistributed (D-003). Put the SNAP CollegeMsg file at `data/CollegeMsg.txt/CollegeMsg.txt`; its SHA-256 must be `e00ba2415373dee52c00616065bcceaa4750e78de60d1855c76470600f10740f`.

## 2. Run the tests

```bash
uv run --frozen pytest
```

## 3. Run the CollegeMsg investigation, free and offline (mock mode)

```bash
uv run --frozen blackgrid run configs/collegemsg_sprint01.json
```

The first run takes about 1.5 minutes: the experiment plus 20 sensitivity replicates. Repeats use the cache and take seconds; add `--no-cache` to recompute everything. The command prints the run folder. Inside it:

- `report.md`: the evidence-linked report;
- `report.html`: the visual console;
- `manifest.json`: hashes, seeds, tool calls, cost;
- the raw artifacts.

To compare with the unvalidated condition (no plan validator, no critic):

```bash
uv run --frozen blackgrid run configs/collegemsg_sprint01.json --condition tool_only
```

## 4. Run the mock pilot (8 synthetic cases × 2 conditions)

```bash
uv run --frozen blackgrid pilot
```

## 5. Open the UI

Each run writes a self-contained HTML console page; `runs/index.html` lists every run and pilot. Rebuild all pages:

```bash
uv run --frozen blackgrid ui
```

Then open `runs/index.html` in your browser. Double-clicking it works, because the pages are fully offline. Or serve the folder:

```bash
uv run --frozen python -m http.server 8765 --bind 127.0.0.1 --directory runs
```

and visit http://localhost:8765/index.html.

The console shows:

- the experiment: observed modularity against the null distribution, ΔQ, z, and p;
- the projected network, coloured by degree and **not** by community;
- the missing-edge sensitivity analysis;
- the agent trace: planner → validator → tools → analyst → critic;
- accepted and rejected claims with reasons;
- the full report and the budget meters.

**Prediction:** Sprint 1 has no predictive model (graph prediction is gated to Phase 3). The UI says so rather than showing invented predictions.

## 6. Live LLM run with OpenRouter (costs money)

Live mode sends **only aggregate statistics and the task text** to the model. It never sends raw events or user IDs. It needs three things:

1. Your key in `.env`, as `OPEN_ROUTER_API_KEY=...` (also accepted: `OPENROUTER_API_KEY`). `.env` is git-ignored.
2. `configs/collegemsg_live.json` (`mode: live`, `paid_execution_authorized: true`). Check `llm.model`; the default `anthropic/claude-haiku-5.5` was **not verified** against OpenRouter's catalogue. If the ID is wrong, the run stops before spending anything and lists similar model IDs.
3. The `--allow-paid` flag on the command line:

```bash
uv run --frozen blackgrid run configs/collegemsg_live.json --allow-paid
```

Before any call, BLACKGRID fetches the model's current price from OpenRouter; if it cannot, it refuses to run. Every call is reserved at its worst case (full `max_tokens`) against these caps:

- 8 calls, 20,000 tokens, and USD 0.50 per run;
- USD 10 for the whole sprint, tracked in `runs/spend_ledger.json`;
- 1 retry per failed call, 2 revision rounds.

A typical validated run makes 2–4 calls.

To re-run a live investigation for free, replay its recorded responses:

```bash
uv run --frozen blackgrid run configs/collegemsg_sprint01.json --mode replay --replay-from runs/<live_run_id>
```

## Exit codes

| Code | Meaning |
|---|---|
| `0` | completed |
| `1` | invalid config, or live mode not authorized or not priced |
| `2` | the run did not complete (abstained, failed, or budget exhausted); see `manifest.json` |

## Layout

| Path | Purpose |
|---|---|
| `src/blackgrid/contracts.py` | Typed contracts: graph, experiment, result, claim, budget, manifest |
| `src/blackgrid/collegemsg.py` | Loader, size-only window selection, projection |
| `src/blackgrid/experiment.py` | Louvain modularity vs degree-preserving null, suitability, verdict rule |
| `src/blackgrid/sensitivity.py` | Missing-edge sensitivity (removed pairs become *unknown*) |
| `src/blackgrid/tools.py` | Allowlisted tools, guarded executor, network guard, cache |
| `src/blackgrid/budget.py`, `providers.py` | Budget ledger; mock / OpenRouter / replay providers |
| `src/blackgrid/agent.py`, `critic.py` | Bounded controller; plan validator and claim critic |
| `src/blackgrid/report.py`, `ui.py` | Evidence-linked report; static HTML console |
| `src/blackgrid/synthetic.py`, `benchmark.py`, `pilot.py` | Synthetic generators, dev benchmark, mock pilot |
| `benchmarks/` | Split policy and public dev registry; `sealed/` is reserved and git-ignored |
| `configs/`, `protocols/`, `docs/` | Run configs, preregistered protocols, decision log, reports |
| `data/` | Raw inputs, read-only and not tracked (only `data/manifests/` is tracked) |
| `runs/` | Run artifacts and UI pages, not tracked |

## Data citation

CollegeMsg: Panzarasa, Opsahl & Carley (2009), *JASIST* 60(5):911–932. Opsahl & Panzarasa (2009), *Social Networks* 31(2):155–163. Source: https://snap.stanford.edu/data/CollegeMsg.html. Use is local and non-commercial under D-003, with no raw redistribution.
