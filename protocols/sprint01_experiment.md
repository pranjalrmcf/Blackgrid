# BLACKGRID — Sprint 1 experiment specification (exp-v1)

Status: **preregistered 2026-10-17, Day 5, before any community statistic was computed on CollegeMsg.** This file fills in the outline in `sprint01_protocol.md` §6. Synthetic development cases may be run freely while building and debugging; the CollegeMsg window may not be analysed under rules other than these. Known in advance (D-016, D-017): the window has 104 nodes, 137 edges and 8 connected components. The thresholds below are set from general principles, not tuned to that graph.

Evidence level for any CollegeMsg result: **descriptive**. The result applies to the observed, projected 7-day window only.

## 1. Hypothesis

- **H1 (exploratory):** The best modularity found in the observed graph exceeds the modularity that the same optimizer finds in degree-preserving randomizations of the graph.
- **Competing explanations:**
  - Degree heterogeneity alone. Hubs raise modularity relative to Erdős–Rényi; the degree-preserving null is chosen to absorb this.
  - Disconnection. Separate components inflate modularity; this is handled by a secondary analysis on the largest component (§5).
  - Sparsity and random fluctuation. Sparse random graphs show high modularity (Guimerà et al. 2004); the null comparison absorbs this.
  - Observation and windowing artefacts. These are addressed by the Day 6 missing-edge sensitivity analysis and stated as limitations.

## 2. Statistic and optimizer

- **Statistic:** Newman–Girvan modularity Q of the best partition found, with resolution 1.0.
- **Optimizer:** Louvain (`networkx.community.louvain_communities`, `resolution=1.0`, default `threshold`). Run **5 restarts with derived seeds; keep the maximum Q.**
- **Same procedure everywhere:** the identical optimizer, restart count and seed derivation are applied to the observed graph and to every null graph (sprint rule: comparable optimization effort).
- **Why Louvain:** it is the standard, fast modularity heuristic. It is stochastic, so best-of-k restarts reduces optimizer noise symmetrically for observed and null graphs. Greedy modularity remains allowlisted but is not used.

## 3. Null model

- **Model:** a degree-preserving double-edge swap Markov chain (configuration model on simple graphs). This is BLACKGRID's own implementation: pick two edges uniformly at random, rewire with probability ½ each way, and reject any swap that would create a self-loop or multi-edge.
- **Burn-in:** target accepted swaps = 10 × m (swaps per edge = 10) per null graph. Each null graph starts from the observed graph with its own derived seed.
- **Attempt cap:** 100 × target attempts. A null graph that does not reach its target within the cap is a **failed replicate**. It is recorded and excluded from the null distribution.
- **Connectivity:** components are **not** preserved; swaps may join or split components. This is deliberate and is why §5 adds a largest-component analysis.

## 4. Inference

- **Replicates R:** fixed by the runtime rule in §7 using development cases only, never by significance.
- **Exceedances:** E = number of successful null replicates with Q_null ≥ Q_obs (ties count as exceedances).
- **p-value:** p = (1 + E) / (1 + R_ok), where R_ok is the number of successful replicates. Resolution is 1 / (1 + R_ok).
- **Effect contrast (reported always, never replaced by p):**
  - ΔQ = Q_obs − mean(Q_null);
  - z = ΔQ / sd(Q_null), descriptive only;
  - the null 5%, 50% and 95% quantiles.
- **Alpha:** 0.05, for one primary test per graph. The secondary largest-component analysis is a robustness check, not a separate claim, so no multiplicity correction applies to the verdict.

## 5. Suitability (abstention) rule

The **primary** analysis uses the whole projected graph. The **secondary** analysis uses its largest connected component (LCC) and runs only if the whole graph is disconnected. Each analysis is *unsuitable*, and abstains, if any of these hold:

| ID | Condition | Rationale |
|---|---|---|
| S1 | fewer than 20 edges | modularity of very small graphs is coarse and unstable |
| S2 | fewer than 10 non-isolated nodes | too few nodes to partition meaningfully |
| S3 | more than 5% of null replicates failed (§3) | the degree sequence leaves the null chain stuck (e.g., stars) |
| S4 | fewer than 95% of successful null graphs differ from the observed graph | the degree sequence nearly determines the graph, so there is no null variation |

S1–S2 are checked before any optimization; S3–S4 after the nulls are generated.

## 6. Verdict rule (deterministic)

| Verdict | Condition |
|---|---|
| `abstain` | primary analysis unsuitable |
| `not_supported` | primary p > 0.05 |
| `supported` | primary p ≤ 0.05, and the graph is connected **or** the LCC analysis is suitable with p ≤ 0.05 |
| `inconclusive` | primary p ≤ 0.05, but the graph is disconnected and the LCC analysis abstains or has p > 0.05 |

Wording rules:

- `not_supported` means "no evidence beyond the null," never "no communities exist."
- `supported` means "modularity exceeds degree-preserving randomizations," never "real friend-groups exist."
- Disconnection is always flagged when present.

## 7. Replicate-count rule (runtime only)

- **Candidates:** R ∈ {99, 199, 499, 999}.
- **Rule:** time one analysis on the development case with the most edges (all dev cases have ≤ 130 edges, comparable to the 137-edge window). Double that time, because a disconnected graph also runs the largest-component analysis. Choose the largest R whose doubled time is at most 30 s, half the 60 s tool cap.
- **Record:** the timings and the choice go in the decision log.
- **Enforcement:** a cooperative deadline aborts the experiment as `failed` when it exceeds the 60 s tool cap.

## 8. Seeds

- **Master seed for CollegeMsg:** 20261017.
- **Derived seeds:** the first 4 bytes of `sha256(master | label…)`, read as an integer below 2^32. The labels are, in order: the analysis scope (`whole_graph` / `largest_component`), then `"observed"` or `"null"` with the replicate index, then `"louvain"` with the restart index.
- **Reproducibility:** identical inputs and seeds reproduce identical results under the locked NetworkX version.

## 9. Prespecified sensitivity (implemented Day 6)

Uniform random removal of **10%** of observed edges, **20** replicates. The full experiment is re-run on each reduced graph, with the same R, seeds derived from the replicate, and the same verdict rule. Report the distribution of Q_obs and ΔQ, and the fraction of verdicts that agree with the full-graph verdict. This is a sensitivity analysis, not an uncertainty interval.

## 10. Out of scope

Out of scope here: alternative resolutions, other optimizers, weighted or directed modularity, partition comparison against generator labels (evaluator-only), and any claim about real social groups, influence or causes.
