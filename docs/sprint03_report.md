# BLACKGRID — Sprint 3 report

18 October 2026. Evidence level: **descriptive, exploratory synthetic evaluation**.
The planned offline implementation is complete. Human review and real-model efficacy
are separate follow-ups; neither is claimed here.

## What was delivered

The single command `blackgrid sprint3 --output runs/NEW_DIRECTORY` freezes source,
protocol, dependency and experiment identities before generating cases, executes the
paired mock workflow and method comparison, scores saved artifacts independently,
and exports a condition-blinded review sheet. Existing experiment implementations,
CollegeMsg windows, historical reference results and Louvain defaults are preserved.

| Acceptance requirement | Evidence |
|---|---|
| New versioned protocol, limits and attempts | [s3-v1.2](../protocols/sprint03_evaluation.md); local `runs/sprint3-v1.1/freeze.json`, `attempts.jsonl`, `suite.json` |
| 24 deterministic validation instances, no exact development-hash overlap | [public registry](../benchmarks/validation/registry.json); `validation.py`; sealed tests unopened |
| Real CPU Louvain–Leiden comparison | 18 structural graphs × 3 seeds, 99 shared null graphs per suitable scope; [method summary](../results/sprint03-v1.1/method_summary.json) |
| Independent artifact evaluation | `evaluation.py`, importing no critic/pilot scoring functions; numerical and integrity oracles |
| Matched offline conditions and failures | All 48 case-condition pairs retained in [summary](../results/sprint03-v1.1/summary.json) and local `evaluation.json` |
| Blinded human-review export | [81 claims](../results/sprint03-v1.1/blinded_claims.csv); mapping remains evaluator-private under ignored `runs/` |
| Full CollegeMsg ingestion | [Ingestion verification](../results/full-collegemsg-v1/VERIFICATION.md), separate from synthetic scores |
| Verification and explanation | 209 regression tests passed; [plain-English guide](sprint03_guide.md); local audit/reproduction receipts |

## Independent agent evaluation

These are the **fixed mock's** final claims, not live LLM answers. Each graph was
examined in both conditions without a tool cache, using the same experiment seed,
five Louvain restarts, 99 null replicates and three uniform edge-removal sensitivity
replicates. Invalid requests share the same maximum budgets but may end earlier.

| Metric | Tool only | Validated |
|---|---:|---:|
| Assessed case-condition pairs | 24 | 24 |
| Workflow-complete cases | 21/24 | 24/24 |
| Evidence-consistent task verdicts | 5/24 | 24/24 |
| Fully supported useful answers | 0/24 | 20/24 |
| Unsupported / assessed claims | 45/45 (100%) | 8/36 (22.2%) |
| Unassessed claims | 0 | 0 |
| Cases with no assessed claims | 3 | 6 |
| Correct explicit refusals | 0/6 | 6/6 |
| Failed / missing-analysis cases | 3/24 | 0/24 |
| Scientific abstentions | 0 | 0 |
| Generator-expectation matches | 9/24 | 23/24 |
| Evidence-supported positive verdicts recovered | 4/4 | 4/4 |
| Fully supported useful positive answers | 0/4 | 0/4 |
| Mock calls | 45 | 56 |
| Estimated mock input + output tokens | 39,820 | 58,746 |
| Paid cost | USD 0 | USD 0 |

Evidence: `summary.json#/evaluation`, local `evaluation.json#/rows`, and hash-verified
investigation manifests. A completed workflow does not necessarily answer the task
correctly. In tool-only mode three arbitrary-method requests fail at the allowlist;
the three causal requests run descriptive analysis instead of giving the required
causal refusal. These are retained failures, not dropped cases.

For the 24 paired graphs, validated-minus-tool-only useful-answer coverage is
**+0.833**, with a paired graph-bootstrap percentile 95% confidence interval
**[+0.667, +0.958]**. On the 18 pairs with assessed claims in both conditions,
the macro unsupported-fraction difference is **−0.778**, interval **[−0.944, −0.556]**.
The six refusal pairs have no validated claims and are excluded from the latter
claim-fraction comparison, while remaining in task coverage denominators.
These intervals resample whole cases using 2,000 fixed-seed draws. They describe
this exploratory scripted case mix; they are not real-model efficacy estimates.

The independent rubric exposed eight claims the critic accepted: four use
“strong community structure” without an operational strength threshold; four state
that observed modularity exceeds the null mean without citing the observed value.
The four affected positive cases therefore fail the strict all-claims-supported
usefulness gate. Both conditions recover their four positive **verdicts**, but neither
delivers a completely supported useful positive answer under this rubric. The main
research thesis—fewer unsupported claims while preserving useful discoveries—is
**not established** by this sprint.

One degree-heterogeneous case differs from the generator expectation under the
agent's frozen seed. A generator family is not a known significance answer for
every finite graph. No cases or seeds were replaced to improve that match.

## Louvain and Leiden

Both adapters optimize the modularity-equivalent objective at resolution 1; all
reported Q values are recomputed through NetworkX. Conversion preserves every node,
including isolates. Partition coverage/disjointness and induced-community connectivity
are checked. Leiden uses two refinement iterations per restart; Louvain uses its own
convergence rule. Equal restart counts do not equalize compute or search procedures.

| Descriptive result over 18 graphs × 3 seeds | Louvain | Leiden |
|---|---:|---:|
| Completed primary comparisons | 54 | 54 |
| Supported final graph-seed decisions | 12 | 11 |
| Not-supported decisions | 24 | 25 |
| Inconclusive decisions | 18 | 18 |
| Disconnected communities in selected observed partitions | 0 | 0 |
| Primary optimizer time, observed + null fits | 38.92 s | 17.03 s |

Evidence: `method_summary.json#/methods`; each full local method artifact retains
shared-null hashes, swap diagnostics, all null Q values, observed partitions,
Monte Carlo exceedance counts, p-values, largest-component checks and timings.
Time excludes shared null-generation cost and is a descriptive measurement on one
CPU setup, without randomized order or warmup. It is not a general speed benchmark.

Leiden's observed Q is higher in 26/54 graph-seed pairs, tied within 1e−12 in 23,
and lower in 5. Mean Leiden-minus-Louvain Q is **0.003185**, range
**[−0.01125, +0.022083]**. These 54 pairs contain only 18 independent generated
graphs; repeated seeds are not extra independent samples. Both methods' decisions
vary across seeds on `val-006` and `val-010`. Seed stability is also reported as
variation of information in natural-log units, without interpreting partition
agreement as recovery of real communities.

The disconnected cases require a component analysis; their small largest components
fail suitability checks, so high whole-graph modularity is not a supported overall
community conclusion. Masked observations also prevent an unqualified supported
conclusion. Both methods receive exactly the same randomized graphs. Finite swaps
are not proof of mixing or an exact conditional null. These are exploratory
comparisons with no confirmatory multiple-method significance claim. **Louvain stays
the default.** No finding establishes friendship, influence or a causal effect.

Adapter design follows the [official Leiden reference](https://leidenalg.readthedocs.io/en/stable/reference.html)
and [Traag, Waltman and van Eck's paper](https://arxiv.org/abs/1810.08473).
The optional backend versions are igraph 0.11.9 and leidenalg 0.10.2, using GPL-family
licenses. They are locked and not vendored; distribution must honor their terms.

## Verification, attempts and reproducibility

The full regression suite passed **209 tests in 107.46 seconds**. New checks cover
fresh graph separation, answer-free inputs, no sealed-case loading, nonconsecutive
node conversion and isolates, known modularity, shared degree-preserving nulls,
partition integrity, disconnected/missingness verdicts, independent numeric binding,
tampering, causal-task scoring, unscorable denominators, budget termination and
output overwrite refusal. No test result is inferred from another environment.

The completed authoritative run is `runs/sprint3-v1.1` (280.11 seconds). A separate
audit recomputed all 48 row scores and summaries, verified hashes, and checked the
saved arithmetic and partition scores for all 54 method comparisons. The clean
environment was built offline from the frozen lock and cached packages.

Earlier failures remain local and visible:

1. `runs/sprint3-v1` (280.61 seconds) is partial because evaluator v1 confused a
   causal-refusal expectation with the separate descriptive test verdict. Three rows
   were unscored. The corrected protocol explicitly records prior inspection;
   these instances are no longer unseen validation data.
2. `runs/sprint3-source-v1.1/runs/reproduction` was interrupted because the source
   archive omitted the inherited HTML template. `interruption.json` records the stop;
   existing files were preserved. A manual interruption can leave the suite root's
   status at `running`, so the supplemental cancellation receipt disambiguates that
   attempt. This is a remaining orchestration limitation, not a scientific result.
3. The complete source snapshot includes that template, verified against the recorded
   Git revision, alongside hashes of the frozen Python source. No scientific code or
   settings changed for its reproduction. The full reproduction completed in
   **284.99 seconds** at `runs/sprint3-source-v1.1-complete/runs/reproduction`.
   All **48 case-condition scores and 54 method graph-seed artifacts matched**,
   including graph hashes, null samples, partitions and decisions, after excluding
   timings, run-directory names and token estimates. Both executions passed the
   independent audit. See `summary.json#/reproduction` and
   `summary.json#/reproduction_verification` for the saved receipts.

Reproduction is the same instances run again, not additional independent evidence.
Timings, run-directory identities and estimated token counts may vary; graph hashes,
null samples, partitions, scores and decisions must match. No paid calls, GPU rental,
external tracing, cloud provisioning, raw-data export, commits or pushes were used.
No reliable human-effort measurement was made; the sprint's 14-hour estimate is not
reported as actual effort. Machine durations and call counts remain in local receipts.

## Limitations and next step

The evaluator is independent code, written in the same project, with a narrow
whitelist of mock prose. It is not a blinded human judgment or a complete semantic
verifier. Human review of the 81 exported claims remains pending. Mock revisions are
scripted and favorable to the critic; no efficacy, calibration, generalization,
novelty, publication-readiness or FDR-control claim is justified.

The generators reuse development families and parameters with fresh seeds, not a
held-out family. Current tools are trusted; network denial and deadlines are
in-process/cooperative and host memory is not OS-limited. The inherited prompt says
20 sensitivity replicates while validation enforces three; this was disclosed before
execution and cannot establish live-model comprehension of that description.

CollegeMsg remains separate: 59,835 local observed events, 1,899 active users and
13,838 undirected pairs, with 37 exact duplicates retained. These descriptive
aggregates neither supply community truth nor authorize full-network inference.
The local-use decision is not a raw-data redistribution license.

The next smallest scientific task is blinded human review of the exported claims.
Use its disagreements to design a new critic/evaluator version, then freeze fresh
validation cases before measuring any improvement. Address the documented manual
interruption status limitation separately. A paid real-model trial still needs an
explicit budget and authorization.
