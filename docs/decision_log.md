# BLACKGRID — decision log

Append-only. Each entry: ID, date (UTC), decision, rationale, status. Never edit a past decision; supersede it with a new entry.

## Sprint 1

### D-001 — Sprint 1 started at Day 1 (2026-10-17)
- **Decision:** The user asked to begin Sprint 1, Day 1, and not to proceed to Day 2 automatically.
- **Scope of authorization:** Day 1 documentation and read-only provenance checks only. Repository scaffolding, environment locking, and code (Day 2+) wait for a separate request.
- **Status:** active.

### D-002 — Local CollegeMsg file accepted as consistent with the SNAP release (2026-10-17)
- **Decision:** Treat `data/CollegeMsg.txt/CollegeMsg.txt` (SHA-256 `e00ba241…10740f`) as the Sprint 1 input.
- **Rationale:** An aggregate streaming check found 59,835 valid rows, 0 malformed rows, and 1,899 distinct node IDs. Span is 193.71 days, and the file is time-sorted. This matches SNAP's published 59,835 temporal edges, 1,899 nodes, and 193 days. Duplicates, self-loops, and the static-edge count are deferred to the Day 3 tested loader.
- **Status:** accepted.

### D-003 — Usage rights: no license found; analytical use awaits user decision (2026-10-17)
- **Findings:** The SNAP CollegeMsg page, the SNAP dataset index, and the Opsahl datasets page state no license, terms of use, or redistribution grant. Both sources request citation. Opsahl withholds node attributes because of re-identification risk.
- **Decision (now):** Raw-record redistribution is treated as **not permitted**. Reports carry aggregate statistics only, plus both citations.
- **Open question for user:** Accept local, non-commercial analytical use with citation as sufficient for Sprint 1? Or keep the real-data run blocked pending further rights confirmation (e.g., contacting the dataset hosts)?
- **Until answered:** The CollegeMsg run is **blocked**. Synthetic workflow proceeds normally.
- **Resolution (2026-10-17, user decision):** The user accepts local, non-commercial analytical use of CollegeMsg with citation for Sprint 1. No raw redistribution. The CollegeMsg run is **unblocked** for Sprint 1 only. Raw records stay local and out of commits, artifact bundles, prompts, and traces. Reports carry aggregates plus both citations. The rights basis is the user's acceptance of the source pages' citation requests, not a verified license. Revisit before any public release (Phase 7).
- **Status:** resolved for Sprint 1.

### D-004 — Window/projection contract frozen before analysis (2026-10-17)
- **Decision:** Adopt the window rule from `PROJECT_CONTEXT.md` as written: earliest `[t0, t0+d)` with d ∈ {7d, 3d, 1d, 6h}, first one with ≤1,000 active nodes and ≤10,000 unique undirected pairs. `t0` = 1082040961. Projection details are in protocol §5.
- **Rationale:** Size-only selection, fixed before any community result exists, prevents favorable-window selection.
- **Note:** The window is deliberately not computed on Day 1. The first recorded selection must come from the Day 3 loader under test.
- **Status:** frozen (changes require a new protocol version).

### D-005 — Resource and spending limits for Sprint 1 (2026-10-17)
- **Decision:** CPU only, one worker, 2 GB memory, 60 s per tool. Mock mode is the default. **No paid API, cloud, or GPU use authorized.**
- **Machine:** Core Ultra 9 185H, 31.7 GB RAM, Python 3.11.9, `uv` and `git` present. The reported GPU VRAM (4,095 MB) is a known Windows WMI 32-bit cap and is not reliable, but this is irrelevant because Sprint 1 uses no GPU.
- **Status:** active.

### D-006 — Day 1 artifact locations (2026-10-17)
- **Decision:** Protocol at `protocols/sprint01_protocol.md`; this log at `docs/decision_log.md`. These follow the suggested repository areas in `PROJECT_CONTEXT.md`. No other directories were created.
- **Status:** active.

### D-007 — Day 2 authorized; Day 3 waits for approval (2026-10-17)
- **Decision:** The user asked to begin Day 2 and to wait for approval before Day 3. Day 2 scope: repository, locked environment, contracts, and one offline entry point. No loader, window computation, or experiment.
- **Status:** active.

### D-008 — Raw data and run outputs excluded from version control (2026-10-17)
- **Decision:** Added `.gitignore` excluding `data/*` (except `data/manifests/`) and `runs/`. The repository has a GitHub remote, and an earlier `.gitignore` containing `data/` had been deleted.
- **Rationale:** D-003 forbids redistributing the raw records. Run artifacts may contain derived records.
- **Status:** active. Nothing has been committed or pushed.

### D-009 — Minimal locked environment (2026-10-17)
- **Decision:** Python 3.11.9 via `uv` 0.11.32, with lockfile `uv.lock`. Runtime dependencies are `networkx` 3.6.1 and `pydantic` 2.13.5. The only dev dependency is `pytest` 9.1.1. Build backend: hatchling.
- **Rationale:** NetworkX is the single graph library proposed in `PROJECT_CONTEXT.md`. Pydantic provides typed, validated specifications. NumPy, SciPy, and others wait until an implemented step needs them.
- **Supply-chain rule:** `exclude-newer = 2026-10-03` makes resolution use only releases at least two weeks old.
- **Status:** active.

### D-010 — Contracts encode protocol invariants (2026-10-17)
- **Decision:** `src/blackgrid/contracts.py` defines frozen, extra-field-forbidding models: `DatasetSource`, `WindowRule`, `ProjectionRule`, `GraphRecord`, `ExperimentSpec`, `ExperimentResult`, `Claim`, `RunConfig`, `CostRecord`, and `RunManifest`. Rules enforced at validation time:
  - The window candidates and size caps are frozen.
  - Real-graph analysis is blocked unless rights are accepted.
  - `GraphRecord` cannot carry generator truth.
  - Proxy edges are not counted as observed, and UNKNOWN is distinct from KNOWN_NON_LINK.
  - Methods and null models are allowlisted, with at least 19 null replicates.
  - The p-value must equal `(1+exceedances)/(1+replicates)`.
  - Failures and abstentions must state a reason.
  - Factual claims need evidence links, and causal claims need an identification argument.
  - Live mode requires paid authorization, and network access cannot be enabled.
  - Budgets are capped at the sprint ceilings, and offline runs must record zero cost.
- **Placeholders, not choices:** the method candidates (`louvain`, `greedy_modularity`), the null models, and the replicate bounds. The single method, statistic, replicate count, and sensitivity condition are frozen on Day 5 before execution.
- **Status:** active.

### D-011 — Offline entry point (2026-10-17)
- **Decision:** `blackgrid validate CONFIG` and `blackgrid run CONFIG` (also `python -m blackgrid`). Until the pipeline exists, `run` writes a FAILED manifest with `not_implemented` and exits 2 rather than producing any result.
- **Status:** active.
