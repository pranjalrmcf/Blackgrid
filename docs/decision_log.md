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

### D-022 — Day 5 authorized (2026-10-17)
- **Decision:** The user asked to begin Day 5. Day 6 waits for a separate request.
- **Status:** active.

### D-023 — Experiment specification exp-v1 preregistered (2026-10-17)
- **Decision:** `protocols/sprint01_experiment.md` was written before any community statistic was computed on any graph. It fixes:
  - the statistic and optimizer: Louvain modularity, best of 5 restarts, resolution 1.0;
  - the null model: an in-house degree-preserving double-edge swap with 10 accepted swaps per edge and a 100× attempt cap; failed replicates are recorded and excluded;
  - the p-value: (1+E)/(1+R_ok), ties counted as exceedances;
  - the effect contrast: ΔQ and z;
  - alpha 0.05;
  - suitability rules S1–S4: ≥20 edges, ≥10 non-isolated nodes, ≤5% failed nulls, ≥95% of nulls distinct from the observed graph;
  - a secondary largest-component analysis for disconnected graphs;
  - a deterministic four-way verdict rule;
  - seed derivation, with CollegeMsg master seed 20261017;
  - the Day 6 sensitivity condition: uniform 10% edge removal, 20 replicates.
- **Pre-execution amendments, made before any result existed:**
  - §8 now names the analysis scope as the first seed label.
  - §7 doubles the measured time to budget for the secondary analysis.
- **Known in advance:** the window's size and 8 components (D-016, D-017). The thresholds are generic, and the window clears S1/S2 by a wide margin regardless.
- **Contract change:** `ExperimentSpec` gains `swap_attempt_factor`, `optimizer_restarts`, `resolution`, `alpha`, `secondary_largest_component`, and `suitability` (`SuitabilityRule`).
- **Status:** frozen.

### D-024 — Replicate count R = 499 by the runtime rule (2026-10-17)
- **Measurement** (`scripts/select_replicates.py`, dev-003, 130 edges, single analysis): R=99 took 1.6 s, R=199 took 3.6 s, R=499 took 8.7 s, R=999 took 17.6 s.
- **Choice:** R=999 doubled is 35.3 s, over the 30 s budget, so R = **499** (doubled 17.5 s). p-value resolution is 0.002.
- **Basis:** chosen on runtime alone, before any CollegeMsg statistic existed.
- **Status:** frozen.

### D-025 — Numerical verification (2026-10-17)
- **Oracles in `tests/test_experiment.py`:**
  - Hand-computed modularity: barbell of two triangles Q = 5/14; two disjoint triangles Q = 1/2; a single community Q = 0.
  - The in-house modularity matches NetworkX on 80 random partitions to 1e-12.
  - Louvain recovers the known barbell optimum.
  - Swaps preserve degrees and simplicity exactly; a star admits no valid swap (it abstains via S3).
  - Quantiles match `statistics.quantiles`.
  - The verdict rule is checked against all branches.
  - Full runs are reproducible; the deadline aborts; oversized graphs are rejected.
- **Status:** 90 tests pass.

### D-026 — Development check of exp-v1, R=499 (2026-10-17; evaluator-side, dev only)
- **Results** (`scripts/dev_check.py`; local output `runs/dev_check/day5.json`):

  | Case | Verdict | Q_obs / null mean | Notes | Key |
  |---|---|---|---|---|
  | dev-001 | supported | 0.542 / 0.274 | z 17.1, p 0.002 | ✔ |
  | dev-002 | not_supported | 0.368 / 0.366 | p 0.44 | ✔ |
  | dev-003 | not_supported | 0.369 / 0.364 | p 0.30; degree confound absorbed | ✔ |
  | dev-004 | not_supported | — | p 0.72 | ✔ (any verdict acceptable) |
  | dev-005 | inconclusive | — | flagged disconnected; LCC unsuitable (S1) | ✔ |
  | dev-006 | supported | — | p 0.002, LCC p 0.014 | **✘** |
  | dev-007, dev-008 | — | — | not scored: refusal is decided before any experiment (Days 7–9) | — |

- **dev-006 failure:** The key expects `inconclusive`/`abstain` with an `incomplete_observation` flag. The experiment ignores the 130 UNKNOWN pairs recorded in the graph record. **The key is not changed after seeing this result.** Handling UNKNOWN pairs (at minimum flagging incomplete observation and qualifying the verdict) is Day 6 work.
- **Missing flag:** dev-003's required `degree_confound` flag is not produced by the experiment. Naming the confound is assigned to the critic/report (Days 9–10).
- **Status:** recorded. These are engineering observations, not efficacy evidence.

### D-027 — CollegeMsg experiment frozen in config, not yet executed (2026-10-17)
- **Decision:** `configs/collegemsg_sprint01.json` now contains the exp-v1 `ExperimentSpec` (config SHA-256 `264459a3…ac44c0`). `blackgrid run` executes it after the window stage and writes `experiment_report.json`. The run still ends `not_implemented` until sensitivity, critic, and report exist.
- **Not done:** the experiment has **not** been run on the CollegeMsg window. The first real-data execution waits for the user's go-ahead.
- **Status:** superseded by D-028 (executed at the user's request).

### D-028 — First CollegeMsg execution of exp-v1 (2026-10-17)
- **Run:** `20261017T123437Z-0c158fa0`, run at the user's request with the frozen spec unchanged (spec SHA-256 `9fac496b…be0000`). Elapsed 18.6 s; 0 failed null replicates; 0 nulls identical to the observed graph; swap acceptance 0.77.
- **Graph:** 104 nodes, 137 edges, 8 components. Largest component: 87 nodes, 127 edges. Mean degree 2.63, max 20, transitivity 0.038.
- **Primary (whole graph):**
  - Q_obs = 0.587; null mean 0.593 (sd 0.012; 5–95%: 0.574–0.614).
  - ΔQ = −0.007, z = −0.57.
  - E = 358 of 499, **p = 0.718**.
- **Secondary (largest component):**
  - Q_obs = 0.543; null mean 0.535.
  - ΔQ = +0.008, z = +0.64.
  - E = 125 of 499, p = 0.252.
- **Verdict (exp-v1 §6):** `not_supported`, flagged `disconnected`.
- **Evidence label:** descriptive. The observed window's modularity is typical of degree-preserving randomizations of itself. This is *no evidence beyond the null*; it does not show that communities are absent. It applies only to the projected first-week window.
- **Pending:** the Day 6 missing-edge sensitivity analysis and the Days 9–10 critic/report have not run. No report claim exists yet.
- **Status:** recorded. The result is not to be revisited by changing the window, method, or thresholds.

### D-029 — Full Sprint 1 authorized, plus a UI and a live adapter (2026-10-18)
- **Request:** The user asked to implement the rest of Sprint 1 (Days 6–14), explained how to run it, built a "futuristic UI" for analysis, experimentation, and prediction, and supplied an OpenRouter key in `.env` for testing.
- **UI deviation, user-requested:** Sprint 1 and `AGENTS.md` exclude a UI or dashboard. The UI is built as the smallest form that meets the request:
  - static, self-contained HTML pages generated from run artifacts;
  - no server, framework, external assets, or new dependencies.
  - All artifact and model text is HTML-escaped, and node identifiers are never shown.
- **Prediction:** Sprint 1 has no predictive model (Phase 3 gate). The UI and report state this rather than inventing predictions.
- **Secrets:** `.env` was untracked and absent from history. It is now git-ignored. The key is read at run time, never logged, and never printed in this session.
- **Live spend:** authorizing a live *capability* is not authorization for this agent to spend. No live call was made (D-035).
- **Status:** active.

### D-030 — exp-v1.1 amendment (2026-10-18)
- **Where:** `protocols/sprint01_experiment.md` §11.
- **Disclosure:** written after D-026 (dev-006 failure) and D-028 (CollegeMsg `not_supported`), and before any sensitivity analysis ran.
- **Changes:**
  - **A.** Unobserved (UNKNOWN) pairs add an `incomplete_observation` flag and downgrade `supported` to `inconclusive`.
  - **B.** A `degree_confound` disclosure is added when max degree ≥ 5 × median.
  - **C.** Sensitivity replicates use R_sens = 99, by runtime; each replicate is its own bounded call.
  - **D.** Sensitivity agreement is measured on raw verdicts.
- **Effect on CollegeMsg:** the primary verdict is unchanged; only the `degree_confound` flag is added.
- **Caveat:** rules A and B are development-driven, so they must be re-checked on fresh validation cases before any confirmatory use.
- **Status:** frozen.

### D-031 — Days 6–12 implementation (2026-10-18)
- **Modules:**
  - `sensitivity.py`: removed pairs become UNKNOWN.
  - `tools.py`:
    - allowlist of `profile_graph`, `community_test`, `edge_removal_sensitivity`;
    - strict argument schemas and a 2 KB request cap;
    - prerequisite and preregistration checks, and graph-size caps;
    - an in-process network guard and a cooperative deadline;
    - a deterministic cache;
    - answer-key markers stop the run.
  - `budget.py`: worst-case reservation before each call; caps on calls, tokens, USD per run and per sprint (persisted), retries, and revisions.
  - `providers.py`: mock (default), OpenRouter (live, gated, pricing fetched first), replay (prompt-hash verified).
  - `agent.py`: bounded planner → validator → executor → analyst → critic → reviser loop.
  - `critic.py`: rubric `critic-v1`, rules R1–R7, plus the pre-execution plan validator.
  - `report.py`: evidence-linked items, with every number checked against cited values. A failing check fails the run.
  - `pilot.py`: evaluator `eval-v1`.
  - `ui.py`, `runner.py`, and the CLI commands `run`, `pilot`, `ui`.
- **Contract additions:**
  - `RunConfig.condition`, `question`, and `llm`;
  - `ToolCallRecord.cached`;
  - `Analysis.null_values`;
  - `CommunityTestReport.raw_verdict` and `unknown_pairs`.
- **Bug found and preserved:**
  - *Failure:* the first pilot (`runs/pilot-20261018T055227Z`) used a mock planner/analyst that read `request` from the wrong level of its input. So the scripted mock never exercised the invalid-method (dev-007) or causal (dev-008) requests in the tool_only condition.
  - *Fix:* corrected, with a regression test added.
  - *Record:* that pilot is kept as a failed attempt and superseded by D-032.
- **Known enforcement gaps (stated, not hidden):**
  - There is no OS-level sandbox.
  - Worker memory is not capped on Windows; the graph-size cap is the proxy.
  - The timeout is a cooperative deadline inside trusted tools, not a hard kill.
  - The network guard is in-process. It blocks Python sockets, not native code.
- **Status:** active.

### D-032 — Mock pilot results (2026-10-18; `runs/pilot-20261018T055709Z`, mock, eval-v1)
- **Summary** (8 dev cases per condition):

  | Metric | tool_only | validated |
  |---|---|---|
  | Useful coverage | 2/8 | 8/8 |
  | Correct verdict | 3/8 | 8/8 |
  | Required flags present | 3/8 | 8/8 |
  | Unsupported claims | 7/15 = 0.47 | 0/12 |
  | LLM calls | 16 | 19 |
  | Tokens | 13,288 | 19,931 |
  | Failures | 0 | 0 |
  | USD | 0 | 0 |

- **What these numbers are:** a check of plumbing and of the critic's catch rate on mistakes I scripted into the mock.
- **What they are not:** evidence that criticism helps a real model.
- **Why the validated condition looks favourable:**
  - eval-v1 shares rules with critic-v1 (numbers, causal language);
  - rules A and B were added after seeing dev failures.
- **Status:** recorded, labelled exploratory/plumbing.

### D-033 — CollegeMsg full investigation, mock mode (2026-10-18)
- **Runs:** `20261018T055724Z-75fab7` (computed), plus cached re-run `20261018T060002Z-08aab6`.
- **Primary:** verdict `not_supported`, unchanged from D-028: Q = 0.587, null mean 0.593, p = 0.718. The largest-component analysis gives p = 0.252. Flags: `disconnected`, `degree_confound`.
- **Sensitivity** (10% uniform removal, 20 replicates, R_sens = 99): 20 of 20 raw verdicts agreed (`not_supported`). Reduced-graph Q ranged 0.593–0.632.
- **Critic:** rejected both naive drafts (R6 structure, R7 comparison) and accepted 2 revised descriptive claims. The report passed the number check. Status `completed`.
- **Caveat:** the analyst text is scripted (mock). Only the statistics are real.
- **Status:** recorded.

### D-034 — Clean-environment reproduction (2026-10-18)
- **Setup:**
  - Repository files were copied into a fresh folder with no `.venv`, `runs`, cache, `.env`, or raw data.
  - A fresh environment was built by `uv sync --frozen --offline`.
  - The data was read from its original location via `--data-root`.
- **Test result:** 137 passed, 1 skipped. The skip is the real-file test, which needs data in the folder by design.
- **Rerun:** `blackgrid run --no-cache`, mock, offline, completed in 94 s.
- **Comparison:** apart from timings and run IDs, the result is identical to `20261018T055724Z-75fab7`: graph record, profile, experiment report (all 499 null values), sensitivity, report, claims, and LLM prompt hashes.
- **Tolerated nondeterminism:** wall-clock timings, run IDs, and timestamps.
- **Status:** first slice reproduced.

### D-035 — Live mode gated; not exercised by the agent (2026-10-18)
- **Gates:** live requires `paid_execution_authorized: true` in the config (`configs/collegemsg_live.json`) **and** `--allow-paid` at invocation **and** a key in env/`.env`. OpenRouter pricing is fetched before any call; if it is unavailable, nothing is sent.
- **Model:** the default `anthropic/claude-haiku-5.5` is unverified; an attempted catalogue lookup returned no pricing fields.
- **Test coverage:** the OpenRouter HTTP path is tested only through its refusal paths and redaction (no paid calls made). Its first real call is untested.
- **Status:** active.

### D-036 — Model ID read from `.env` (2026-10-18)
- **Decision:** At the user's request, live mode reads the OpenRouter model ID from `OPEN_ROUTER_MODEL` (or `OPENROUTER_MODEL`) in the environment or `.env`. It overrides `llm.model` in the config.
- **Recording:** the override is applied to the run config itself, so `config.json` and the config hash record the model actually used.
- **Scope:** mock and replay modes ignore `.env`.
- **Files:**
  - `OPEN_ROUTER_MODEL=anthropic/claude-haiku-5.5` was appended to the user's `.env` (the key line is untouched; values were never printed);
  - `.env.example` (placeholders only) is committable via a `.gitignore` exception.
- **Status:** active. The model ID is still unverified (D-035).

### D-037 — First live run failed on truncated replies; fixed (2026-10-18)
- **Run:** `20261018T061010Z-7e90d5` (user-run, live, validated).
  - OpenRouter resolved `anthropic/claude-haiku-5.5` at $0.10/M input and $0.50/M output tokens.
  - 3 calls, $0.0020.
- **Failure:** The planner succeeded. Both analyst replies hit `max_tokens_per_call` (1,200 completion tokens), were cut off mid-JSON, and the run failed with `analyst_failed: schema`. The retry resent the identical prompt.
- **What the trace shows:** the model's draft claims were accurate and correctly cited, just too many. Completion tokens greatly exceeded the visible text, which suggests the model also spends completion tokens on internal reasoning.
- **Fix (prompts-v2):**
  - Read `finish_reason`; a `length` reply is never parsed and is reported as truncated.
  - The retry carries a corrective note asking for fewer, shorter claims.
  - The analyst is limited to at most 5 claims under 35 words each.
  - The default per-call cap rises from 1,200 to 2,000 tokens; the per-run cap of 20,000 is unchanged.
  - A revision that the budget cannot afford now drops the rejected claims instead of failing the run.
- **Tests:** regression tests added. 141 tests pass.
- **Record:** the failed run is preserved. The fix is **not yet verified live**.
- **Status:** active.

### D-038 — Number checks: no bare x100, labelled numbers must match their meaning (2026-10-18)
- **Trigger:** an external review (Codex), confirmed against the code.
- **Problems found:**
  - `number_matches` accepted value × 100 even without a `%` sign, so a cited Q of 0.587 could "support" `Q = 58.7`.
  - Any cited value could support any number, so `Q = 0.593` passed when the null mean (0.593) was cited.
- **Fix (critic-v2, eval-v2):**
  - ×100 applies only to numbers written with `%`.
  - Numbers attached to a label must match a cited field of that meaning. The labels are Q/modularity, p, z, null mean, sd, and delta Q.
  - The rule is applied in the critic, in the report number check, and in the pilot evaluator.
- **Effect on results:** none. CollegeMsg and the pilot give identical results under v2.
- **Status:** active.

### D-039 — Spending caps made hard limits (2026-10-18)
- **Trigger:** external review, confirmed in the live artifacts.
- **Evidence:** in run `20261018T061637Z-89dcc9`:
  - the first call was reserved at $0.000654;
  - list price × tokens was $0.000650;
  - OpenRouter **reported $0.000908** (1.39× list price), above the reservation.

  Failed calls (HTTP 404) had been booked at only the estimated input cost.
- **Fix:**
  - **Money reservation:** uses a strict prompt bound (UTF-8 bytes + 64 tokens per message) plus the full `max_tokens`, at **2× list price**.
  - **Failed calls:** a call with unknown billing books its whole reservation.
  - **Breach handling:** any charge above its reservation halts all further paid calls, and the run ends `budget_exhausted` with the reason recorded.
  - The token cap still uses the typical estimate.
- **Guarantee and its assumptions:** the caps are hard limits provided the provider honours `max_tokens` and charges at most 2× list price. A breach of those assumptions is detected after one call and stops everything.
- **Status:** active.

### D-040 — Required analyses: no "completed" for a partial answer (2026-10-18)
- **Trigger:** external review.
- **Evidence:** in `20261018T061637Z-89dcc9`, the live planner chose only `community_test` and skipped `edge_removal_sensitivity`, which the question and protocol (exp-v1.1 §9) require. The run was still marked `completed`.
- **Fix:**
  - The plan validator adds any required analysis the planner omitted, and records that it did.
  - In both conditions, a run missing a required analysis ends with the new status **`partial`**. It reports `missing_analyses` and states "PARTIAL ANSWER" in the report and UI.
  - Exit code 2.
- **Reclassification:** that run's stored status is historical and was not edited. Under these rules it is **partial**.
- **Status:** active.

### D-041 — Live run history to date (2026-10-18)

All live runs were made by the user.

| Run | Model | Outcome | Calls | Cost |
|---|---|---|---|---|
| `061010` | `anthropic/claude-haiku-5.5` | failed: truncated analyst (D-037) | 3 | $0.00195 |
| `061353` | `anthropic/claude-haiku-5.5` | failed: HTTP 404 ×2 (the model is listed with a price, but its endpoint returned 404) | 2 | $0.00011 |
| `061609` | `deepseek/deepseek-v4.1-flash` | failed: HTTP 404 ×2 | 2 | $0.00007 |
| `061637` | `deepseek/deepseek-v4-flash-0731` | completed, verdict `not_supported` (planner and analyst each truncated once; retries succeeded; reviser used) | 5 | $0.00293 |

- **Totals:** sprint ledger $0.0051 of $10.
- **On `061637`:** it is *partial* under D-040, because sensitivity was skipped. Its first two truncations returned **0 visible characters**: the model spent all 2,000 output tokens on hidden reasoning.
- **Not yet done:** no live run has used the D-038–D-040 fixes.
- **Status:** recorded.

## Sprint 2

### D-042 — Sprint 2 implementation authorized; Session 1 handoff (2026-10-18)
- **Authorization:** The user added `SPRINT_02.md` and asked to start implementing it. Its header says "plan only"; the user's request supersedes that for implementation. `AGENTS.md`, earlier protocols, and historical decisions are not rewritten.
- **Scope:**
  - six sessions: a LangGraph workflow, a deterministic supervisor, durable operations, authorization, recovery, and visibility;
  - **all checks offline**;
  - **no paid call is authorized by this entry.** The optional live acceptance test needs separate approval, under a USD 1 Sprint 2 ceiling.
- **Regression baseline:** 152 tests pass, including the 12 D-038–D-040 regressions.
- **Reference run:** mock run `20261018T064334Z-09af60` (validated, critic-v2). Its fingerprint is in `benchmarks/reference/collegemsg_mock_reference.json`, made with `blackgrid.parity` (timings and IDs excluded).
- **Contract:** `protocols/sprint02_workflow.md` (wf-v1) defines run outcomes (adding `paused` and `denied`), completion obligations, operation states, retry categories, state contents, budget durability, and authorization.
- **Status:** active.

### D-043 — Dependencies: LangGraph 1.2.12 with the SQLite checkpointer (2026-10-18)
- **Resolved under `exclude-newer = 2026-10-03`:**
  - `langgraph` 1.2.12 (MIT);
  - `langgraph-checkpoint` 4.2.0 and `langgraph-checkpoint-sqlite` 3.1.1 (MIT);
  - `langchain-core` 1.6.6 (MIT).
- **Transitive packages:** MIT, BSD, or Apache, plus `orjson` (MPL-2.0 AND Apache-2.0/MIT).
- **API check:** before use, the installed API was verified to support `interrupt`, `Command(resume=...)`, `SqliteSaver` across fresh connections, and `durability="sync"`.
- **Tracing:** the install pulls in the `langsmith` client. External tracing is forced off (`LANGSMITH_TRACING=false`) when `blackgrid.workflow` is imported, and a test checks it.
- **Not installed:** no agent server, LangChain agent suite, or hosted service.
- **Status:** active.

### D-044 — Workflow implementation and its behaviour changes (2026-10-18)
- **The workflow:**
  - `blackgrid.workflow` implements wf-v1 as one LangGraph state graph: initialize, authorize, plan, validate, execute, check_evidence, analyst, critic/reviser, finalize.
  - A deterministic supervisor decides routing and completion; it is code, not an LLM.
  - Every LLM and tool call is a durable operation (`workflow/store.py`).
  - Pauses use LangGraph interrupts.
- **One implementation:** the old `Controller` now runs this same graph with in-memory services, so there is no second, divergent implementation. All Sprint 1 tests run through the graph.
- **Intended behaviour changes**, as required by `SPRINT_02.md`:
  1. When required evidence is incomplete, the run finalizes as `partial` (or `failed` if no required analysis completed) **without calling the analyst**. Previously tool_only still drafted claims.
  2. Provider errors are classified (D-045):
     - permanent errors (HTTP 400/401/403/404) are not retried;
     - an uncertain error after dispatch pauses for reconciliation instead of retrying.
  3. Live runs without authorization **pause** before the first paid call instead of refusing to start. The config flag is still required at start.
  4. A revision round counts only if its call was actually reserved.
  5. Money caps: the project cap keeps all prior spend (Sprint 1's $0.0051 is imported from `spend_ledger.json`), and a separate **Sprint 2 cap of USD 1** applies.
- **Status:** active.

### D-045 — Retry and reconciliation policy (2026-10-18)
- **Policy, by error category:**
  - `transient` (connection refused before sending, DNS failure, HTTP 429 or 5xx): one retry.
  - `malformed` (a reply that was received but truncated or unparseable): billed, one retry with a corrective note.
  - `permanent`: no retry.
  - `uncertain` (a timeout or reset after sending, or a crash between dispatch and the saved receipt): the run pauses. A person chooses `reconcile --retry` (retry once, within the caps) or `--stop`.
- **Billing:** in every unknown case the full reservation stays charged.
- **Limits:** exactly-once execution is not claimed.
- **Status:** active.

### D-046 — Interactive console (user-requested deviation) (2026-10-18)
- **Request:** mid-Sprint 2, the user asked for "an interactive dynamic UI instead of static UIs", with each run saved as a static template. `SPRINT_02.md` §12.9 said "no new frontend framework or web service"; the user's request overrides that.
- **Smallest form that meets it:** one self-contained template (`console/template.html`, plain JavaScript, no framework, no external assets) used in two modes:
  1. **Live:** `blackgrid console` is a standard-library HTTP server on **127.0.0.1 only**, with:
     - Host-header checks against DNS rebinding;
     - a per-session token on every action;
     - strict CSP and framing headers;
     - a fixed action allowlist routed through the CLI's own code and gates: mock start, pilot, resume, cancel, deny, reconcile;
     - **no paid start or approval from the browser**;
     - one background job at a time.
  2. **Static:** every finished run, pilot, and the index saves the same console with its data embedded (`report.html`, `pilot.html`, `index.html`), interactive offline.
- **Data safety:** data is embedded as JSON with `<`, `>`, and `&` escaped, and the page inserts text only with `textContent` (no `innerHTML`). LLM prompts and receipts are never sent to the browser.
- **Replaces:** the old static HTML builder in `ui.py`.
- **Status:** active.

### D-047 — Sprint 2 verification results (2026-10-18)
- **Tests:** 182 pass. They include:
  - 20 workflow failure tests: crashes before dispatch, after dispatch, after the receipt, after a tool, and during finalize;
  - restart recovery with no repeated calls;
  - reconciliation pause, then retry or stop;
  - caps across restarts;
  - concurrent-resume rejection;
  - authorization pause, approve, expire, mismatch, and deny;
  - cancellation;
  - tampered artifacts;
  - changed config or unknown checkpoint version;
  - checkpoint hygiene;
  - replay with no live fallback;
  - partial on a failed sensitivity;
  - 6 console safety tests.
- **Parity:**
  - The CollegeMsg run through the workflow is **identical** to the Sprint 1 reference fingerprint.
  - It stays identical when recomputed with no cache in a clean, offline environment: 171 passed and 1 skipped there (no data in the clean copy).
  - Mock pilot: **15/16 case-conditions identical**. The exception is dev-007 tool_only, now `failed` with 1 call instead of `abstained` with 2; that is D-044 change 1. Pilot scores are unchanged.
- **Cost:** USD 0 in Sprint 2. No paid call was made.
- **Bugs found and fixed during verification:**
  - a revision counted without a call;
  - a stale stage/status in the console (finalize rendered before publishing);
  - a crash when pricing was missing on a denied run;
  - nested DOM children in the console;
  - the console server rejecting POSTs before reading their body. On Windows this aborted the connection and turned a clean 403 or 415 into a connection error. It was intermittent; the fix was confirmed by three repeated runs.
- **Status:** recorded.
