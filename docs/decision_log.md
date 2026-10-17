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

### D-012 — Day 3 authorized; Day 4 waits for approval (2026-10-17)
- **Decision:** The user asked for Day 3 only, plus a learning guide (`docs/learning_guide.md`).
- **Status:** active.

### D-013 — Loader row policy (2026-10-17)
- **Decision:** The checksum must match before parsing, or the load fails (`DataIntegrityError`).
  - Blank and `#` lines are skipped and counted.
  - Malformed rows are excluded and counted by reason: wrong field count, non-integer, or a negative value.
  - Valid events are kept in file order. Repeated events are preserved, and exact duplicate rows are flagged but kept.
  - Timestamp decreases in file order are counted. Window selection does not rely on sorting.
- **Status:** active.

### D-014 — Projection keeps self-loop-only nodes as isolates (2026-10-17)
- **Decision:** Projection node set = all active nodes in the window. Self-loop edges are excluded and counted. A node whose only events are self-loops stays as an isolated node and is counted as `self_loop_only_nodes`.
- **Rationale:** This keeps the active-node count used by the size cap equal to the projected node count. The selected window has 0 self-loops, so this choice does not affect Sprint 1 numbers.
- **Status:** active.

### D-015 — Synthetic truth isolation tightened (2026-10-17; amends D-010)
- **Decision:** `GraphRecord` no longer contains `GeneratorSpec`; it carries only `generator_sha256`. The spec lives in evaluator-only `EvaluatorTruth`. Fixture IDs are neutral (`dev-001`, `dev-002`). Generator node, edge, and graph attributes are stripped.
- **Rationale:** Day 3 tests found three leaks, each of which would have revealed the answer to a planner:
  - the family `planted_sbm` and `p_in`/`p_out` sat in the record;
  - an ID named `tiny-sbm`;
  - the NetworkX SBM `block` node attribute.
- **Status:** active.

### D-016 — CollegeMsg window selected by the frozen rule (2026-10-17)
- **Result (descriptive, size-only):**
  - The first candidate, 7 days `[1082040961, 1082645761)`, satisfied both caps and was chosen.
  - 196 events (0.33% of 59,835), 104 active nodes, 137 unique undirected edges, 0 self-loops, 0 exact duplicates in the window.
  - Projection SHA-256 `ae2aec6c…ec17fd4`.
  - Full file: 37 exact-duplicate rows (flagged), 0 self-loops, 0 malformed rows. 20,296 distinct directed pairs, matching SNAP's published static-edge count. 13,838 unique undirected pairs.
  - Recorded in `data/manifests/collegemsg.json`, from run `20261017T090845Z-4ea73188`.
- **Known limitation:** The window is small and sparse (mean degree ≈ 2.6). Sparse graphs can show high modularity by chance, so the null comparison is essential, and the graph may prove unsuitable.
- **Rule going forward:** A suitability criterion (e.g., minimum edges, component structure) must be preregistered on Day 5, before any community statistic is computed on this graph. If the window fails it, the run abstains. The window is not changed (D-004).
- **Status:** frozen.

### D-017 — Disclosure: real-window graph visualized before Day 5 (2026-10-17)
- **What happened:** At the user's request, the selected CollegeMsg window was drawn as an unlabeled node-link picture next to the two synthetic fixtures. Output: `runs/figures/networks_day3.png` (git-ignored, local only). The script used temporary `matplotlib`/`scipy`, which were not added to the project dependencies.
- **What was seen:** One main component plus 7 small detached components (8 connected components in total). Several hub-like nodes are visible. No community detection, modularity, or null comparison was run. No node IDs are shown.
- **Implication:** The component structure is now known before the Day 5 suitability criterion is written. This is recorded so that the criterion's choice can be judged with that knowledge in view. The criterion must be justified from general principles (e.g., minimum size and edge count for a meaningful null comparison), not tuned to make this graph pass or fail.
- **Status:** disclosed.

### D-018 — Day 4 authorized (2026-10-17)
- **Decision:** The user asked to begin Day 4. Day 5 waits for a separate request, following the pattern set in D-007 and D-012.
- **Status:** active.

### D-019 — Development benchmark dev-v0.1 (2026-10-17)
- **Decision:** There are 8 synthetic development cases in `src/blackgrid/benchmark.py`. They cover 4 graph families (planted SBM, Erdős–Rényi, degree-heterogeneous, disconnected sparse) and all 4 task types: community evidence, claim vs null, incomplete observation vs fragmentation, and refuse invalid request. The set includes a null, a disconnected graph, a missing-edge (masked) graph, and two invalid requests (arbitrary code; unidentified causal claim). The case-by-case table is in `benchmarks/README.md`.
- **Answer-key design:**
  - Each case splits into a planner-visible `PublicCase` plus graph plus `GraphRecord`, and an evaluator-only `CaseKey` plus `EvaluatorTruth`.
  - `CaseKey` lists *acceptable* verdicts and *required* flags. dev-004 (weak signal) accepts any verdict and exists to check hedged language.
  - A committed public registry (`benchmarks/dev/registry.json`) is tested to contain no leak terms.
- **Missing edges:** dev-006 masks 30% of node pairs as UNKNOWN. The 19 true edges inside the mask are evaluator-only. The mask splits the observed graph into 2 components, while the true graph is connected.
- **Pre-experiment tuning (disclosed):** dev-003's first draft had 9 components and 8 isolates, which confounded "hubs" with "disconnection." The degree-heterogeneous generator now takes a minimum expected degree (3.0) and keeps the largest connected component. This was chosen on connectivity alone. No community statistic had been computed on any fixture.
- **Status:** active. These are engineering fixtures, not efficacy evidence.

### D-020 — Split policy and sealed-test reservation (2026-10-17)
- **Decision:** IDs `dev-NNN`, `val-NNN`, `test-NNN` with disjoint seed ranges: 1–999, 1,000–9,999, and 100,000–999,999. `benchmarks/sealed/` is git-ignored and reserved. Sealed instances are generated only after prompts, evaluators, thresholds, and budgets are frozen.
- **Status:** active.

### D-021 — CollegeMsg parser/window fixtures (2026-10-17)
- **Decision:** 9 small committed event files in `tests/fixtures/collegemsg/`:
  - schema problems, CRLF, whitespace, the half-open boundary, and unsorted input;
  - fallback to 1 day, fallback to 6 hours;
  - node-cap abstention, and an empty file.
- Expected values are hand-derived in `make_fixtures.py` rather than computed by the loader. `.gitattributes` keeps fixture bytes exact.
- **Status:** active.
