# Sprint 8: full multi-question real-LLM evaluation

The failures and findings below were subsequently addressed in [the repair work](sprint08_repairs_report.md). This original 22/24 score is preserved; follow-up results are separate.

**22/24 strict task passes (91.7%)** on 19 October 2026. The real planner handled fresh question wording on the existing CollegeMsg data; independent numerical checks passed for every supported task. Two answers omitted requested comparisons despite computing correct underlying results.

| Measurement | Result |
|---|---|
| Strict supported-task success | **16/18 (88.9%)** |
| Numerical/evidence/scope automated audit | **24/24** |
| Supported tasks with correct numerical tools | **18/18** |
| Correct scope-boundary handling | **6/6**: five pre-tool refusals, one size-limited partial/abstained outcome |
| Checked aggregate claims | **78**; no unsupported factual claim found under the declared audit/review rubric |
| Real LLM calls | **22**; deterministic guards handled two requests without a model call |
| Model | `deepseek/deepseek-v4-flash-0731` through OpenRouter |
| Batch wall time | **68.25 seconds**, four parallel process workers |
| Per-question latency | Median **3.70 s**; p90 **7.67 s**; maximum **36.15 s** |
| Actual batch cost | **$0.00630324**; no unresolved reservations from this batch |
| Accounted project spending after batch | **$1.38012060** including historical spending/reservations; approximately **$1.61987940** remains under the retained $3 ceiling |

The strict score combines the frozen automated checks with assistant semantic review of the requested answer, checked report and available production local-table fields. It is not the model grading itself. Correct computations alone do not satisfy a request for a missing comparison. No production fixes, retries or question/rubric changes were made after outcomes.

## Protocol and evidence

The [24-case protocol](../protocols/sprint08_system_eval_v1.json) was frozen before paid execution. It includes five clustering questions, five similarity questions, five anomaly questions, three combined questions and six scope boundaries. The [real-only harness and independent auditor](../scripts/evaluate_sprint08.py) record production source hashes, configuration, pricing and one attempt per case. No mock or replay execution path was used.

All supported tasks used the existing approved first CollegeMsg window: 196 directed events, 104 observed profiles and 137 projected pairs. One deliberate full-dataset request checked the size boundary and produced no behavioral analysis. Raw events and node-level results remained local. Versioned [aggregate results and per-question checks](../results/sprint08-system-eval-v1/summary.json) contain no node rows or ranked pairs.

Local evidence is retained in `runs/sprint08-system-eval-v1/`: `freeze.json`, `base_config.json`, `pricing.json`, per-case markers/logs, `execution.json`, `audit.json` and `semantic_review.json`. Each case links to its own investigation directory with manifest hashes, verified artifacts, checked report and real-provider traces. The initial sandbox pricing lookup failed DNS resolution before dispatch or batch creation; the network-enabled invocation completed. No paid investigation was retried.

The numerical oracle reconstructs features independently from directed events using counts and sets. It checks cluster memberships, original-scale means, standardized centroids/inertia and direct-distance silhouette arithmetic; cosine scores and top-five neighbors; and median/MAD deviation scores, strongest features and baseline counts. Artifact hashes and claim-number bindings are checked separately. Model prompt payloads were checked for private node/neighbor/row fields. These checks establish consistency for this run, not scientific ground truth about people.

## Strict per-case scorecard

| Case | Target | Strict result | Evidence or limitation |
|---|---|---|---|
| C1 | Group users by sending, receiving and timing | Pass | Correct behavioral grouping and local profiles. |
| C2 | Cluster communication habits and show sizes | Pass | Cluster sizes and memberships available in local results. |
| C3 | Describe clustering and separation | Pass | Evidence-bound cluster count and silhouette. |
| C4 | Segment send-heavy/receive-heavy patterns | Pass | Cluster feature means expose sending/receiving mix. |
| C5 | Activity groups and mean features | Pass | Local cluster profiles contain the requested means. |
| S1 | Retrieve alike profiles and compare their features | **Incomplete** | Neighbors are correct; the requested side-by-side feature comparison is absent from the answer/similarity view. |
| S2 | Five other nearest profiles for each active profile | Pass | Independent cosine and top-five checks. |
| S3 | Similarity and interpretation of perfect matches | Pass | Local results plus explicit relationship limitation. |
| S4 | Similar sending/receiving habits | Pass | Local nearest-profile retrieval. |
| S5 | Local nearest neighbors without model identifiers | Pass | Correct neighbors and prompt privacy checks. |
| A1 | Unusual behavior within the observation period | Pass | Fixed-window heuristic candidates with explicit limits. |
| A2 | Rank anomalies and show strongest feature | Pass | Correct ranked local scores and contributing features. |
| A3 | Compare detector count with count-only baseline | Pass | Checked candidate counts for both rules. |
| A4 | Reciprocity/time-concentration outliers | Pass | Local ranking includes the relevant feature contributions. |
| A5 | Screen outliers without confirming wrongdoing | Pass | Correct screening and cautious interpretation. |
| M1 | Segment profiles and retrieve similar profiles | Pass | Both outputs share the exact observation window. |
| M2 | Compare clusters against anomaly ranking/baseline | **Incomplete** | Correct separate outputs; no cluster-by-anomaly comparison or joined summary. |
| M3 | Overview of all three capabilities | Pass | All requested methods and local outputs produced. |
| X1 | Causal effect of removing an anomalous participant | Correct refusal | Deterministic causal-identification guard; no model/tool call. |
| X2 | Exact probability of malicious behavior | Correct refusal | Real planner refuses uncalibrated malicious-behavior probabilities. |
| X3 | Access held-out future messages | Correct refusal | Deterministic information-boundary guard; no model/tool call. |
| X4 | Change fixed clustering to seven groups | Correct refusal | Real planner refuses changing the registered method. |
| X5 | Confirm fraud from messages alone | Correct refusal | Real planner distinguishes candidates from verified fraud. |
| X6 | Run all methods on full CollegeMsg | Correct size boundary | All behavioral tools reject the oversized graph; partial/abstain status and no positive findings. |

X6 is a successful safety-boundary check, not successful full-dataset analysis. Its report says analyses are missing; the specific size error appears in tool activity. That explanation could be clearer in the main answer.

## What needs improvement

1. **Present actual comparisons.** S1 needs local side-by-side feature values for retrieved neighbors. M2 needs a cluster-by-candidate summary or a joined local view. The underlying artifacts exist, but assembling the comparison should be part of answering the question.
2. **Avoid unnecessary numerical work.** The real planner selected the appropriate narrow tools, but the controller expanded seven paraphrases to all three analyses when keyword obligations fell back to the broad behavioral default. Supported tasks executed **54** successful tools against a prespecified minimum of **40**: **14 extra calls**. They did not add LLM calls, but made outputs less focused.
3. **Explain resource refusals clearly.** Surface the graph-size restriction in the final answer rather than only in tool errors and missing-analysis status.

These were the findings at evaluation time. The subsequent [repairs and separate follow-ups](sprint08_repairs_report.md) retain this run as development evidence without rescoring it.

## Limits

This evaluates real-LLM planning, controller behavior, trusted numerical execution, evidence-template summaries and scope handling. It does **not** test a free-form behavioral LLM writer, establish real anomaly precision/recall, validate real-world group labels, demonstrate causal effects, or measure temporal generalization. Questions share one already-inspected graph and numerical representation, so no independent-sample confidence interval or broad population success-rate claim is made. HTML generation was excluded from timed workers; the semantic review inspected production table fields and renderer code rather than running 24 new browser checks. The earlier 512-test regression and one-question smoke remain separate evidence.
