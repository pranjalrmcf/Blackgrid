# Blackgrid

Bounded, evidence-grounded network-science investigations. Sprint 1 builds one offline, reproducible vertical slice on a bounded CollegeMsg window, with synthetic known-truth checks. Start with `PROJECT_CONTEXT.md`, `SPRINT_01.md`, `AGENTS.md`, and `protocols/sprint01_protocol.md`.

## Status

Sprint 1, Day 4. The loader (checksum and schema checks), the size-only window selection, and the undirected projection are implemented. So is an 8-case synthetic development benchmark with evaluator-only answer keys (`benchmarks/README.md`), plus hand-checked CollegeMsg parser/window fixtures. `run` builds the bounded graph and writes its aggregate artifacts. It then records a **failed** manifest (`not_implemented: experiment`) until Day 5. The aggregate data manifest is at `data/manifests/collegemsg.json`. For a study plan, see `docs/learning_guide.md`.

## Setup (offline after the first sync)

Requires Python 3.11 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --frozen
```

The raw dataset is not distributed (decision D-003). Place the SNAP CollegeMsg file at `data/CollegeMsg.txt/CollegeMsg.txt`. Its SHA-256 must be `e00ba2415373dee52c00616065bcceaa4750e78de60d1855c76470600f10740f`.

## Entry point

```bash
uv run --frozen blackgrid validate configs/collegemsg_sprint01.json
```

```bash
uv run --frozen blackgrid run configs/collegemsg_sprint01.json
```

- `run` executes offline in mock mode. No network, no secrets, no paid calls.
- Each invocation writes `runs/<run_id>/manifest.json` and `config.json` (git-ignored).
- Exit codes: `0` success, `1` invalid config, `2` the run did not complete (failed/abstained; see the manifest).
- Live mode is rejected unless `paid_execution_authorized` is set, which requires separate user authorization.

## Tests

```bash
uv run --frozen pytest
```

## Layout

| Path | Purpose |
|---|---|
| `src/blackgrid/contracts.py` | Graph, experiment, result, claim, and run-manifest contracts |
| `src/blackgrid/cli.py` | Offline CLI |
| `src/blackgrid/collegemsg.py` | Loader, window selection, projection |
| `src/blackgrid/synthetic.py`, `benchmark.py` | Synthetic generators and the dev benchmark |
| `benchmarks/` | Split policy, public dev registry; `sealed/` is reserved and git-ignored |
| `tests/fixtures/collegemsg/` | Hand-checked parser/window fixtures |
| `configs/` | Validated run configurations |
| `protocols/` | Versioned study protocols |
| `docs/decision_log.md` | Append-only decision log |
| `data/` | Raw inputs, read-only and not tracked (only `data/manifests/` is tracked) |
| `runs/` | Run artifacts, not tracked |

## Data citation

CollegeMsg: Panzarasa, Opsahl & Carley (2009), *JASIST* 60(5):911–932. Opsahl & Panzarasa (2009), *Social Networks* 31(2):155–163. Source: https://snap.stanford.edu/data/CollegeMsg.html. Use is local and non-commercial under D-003, with no raw redistribution.
