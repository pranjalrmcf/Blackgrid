# Full real-LLM evaluation v7

**23/24 strict passes (95.8%)**, with one incomplete model answer. All 24 cases were attempted once; no timeouts or not-dispatched cases. This evaluates the current runtime after the complete regression repairs.

| Category | Pass | Total |
|---|---:|---:|
| Community | 4 | 4 |
| Centrality | 3 | 3 |
| Bridges | 3 | 3 |
| Forecasting | 4 | 4 |
| Saved synthetic research | 3 | 4 |
| Unsupported requests | 6 | 6 |

## Failure retained

T-R4 requested the saved synthetic causal estimand, treatment, outcome, adjustment and supplied assumptions. Planning selected the correct research family and causal_identification_check completed. The subsequent real writer response hit max_tokens=8192 and was truncated. Runtime status is failed; the evaluation records an incomplete answer, which remains a non-pass in the 24-case denominator. No retry, local repair or selective replacement was performed.

All three bridge questions passed, including cross-community ranking stability. The previous v6 suite also scored 23/24, but its failure was a substituted bridge target. These are separate fresh-wording exploratory sets, not paired scientific trials or evidence that the remaining failure rate is unchanged.

## Real execution, evidence and cost

- Model: deepseek/deepseek-v4-flash-0731 through OpenRouter. No mock or replay execution. 19 questions used real model calls: all 18 supported requests plus one causal refusal. 5 other refusals were deterministic guards. The four research cases also invoked real writing; 23 receipted model operations total.
- Validated community/structural/forecast summaries used checked local templates. Research review retained its configured writer. This is a system evaluation, not 24 unrestricted model-only responses.
- Four process workers; total 107.66s; median case 6.22s, p90 29.92s, maximum 55.75s.
- Confirmed batch charge USD 0.00890326; new uncertain reservations USD 0.00000000. Receipt files and hashes verified.
- Project conservative accounting USD 1.37352672, including earlier charges and retained reservations; USD 1.62647328 remains within the authorized USD3 ceiling. This is local project accounting, not provider balance.
- Source, protocol and evaluator hashes stayed unchanged during execution. Independent local checks covered manifest hashes, claim/report numbers and links, raw-graph centrality, bridge counts/ranks, community null arithmetic, forecast candidates/cutoff/order and saved metric consistency. Assistant review assessed responsiveness, scope and refusal reasons; no human or independent-model judge is claimed.

## Scientific limits

The questions use familiar task families, reused CollegeMsg evidence and saved synthetic studies. Normal numerical caches were enabled; timing is warm-operation latency. The 24 questions are not independent graphs, and no new model training, predictive benchmark, real-data calibration or causal effect was established. The UI renderer was excluded. Rankings remain local. A passing answer is supported within its registered scope, not a proof of autonomous scientific discovery.

The 493-pass offline regression result and this live result measure different things. A scripted test provider cannot establish that a real writer will honor a response budget. The remaining smallest reliability improvement is to remove unnecessary research rewriting or bound it more tightly, then verify under a separately frozen protocol; that change was not made during this run.

## Per-case review

| Case | Outcome | Review |
|---|---|---|
| T-C1 | pass | Fixed-window null comparison, effect and uncertainty, uniform removal sensitivity and descriptive limitations address the request. A nonsignificant result is not treated as proof of the null. |
| T-C2 | pass | Fixed-window null comparison, effect and uncertainty, uniform removal sensitivity and descriptive limitations address the request. A nonsignificant result is not treated as proof of the null. |
| T-C3 | pass | Fixed-window null comparison, effect and uncertainty, uniform removal sensitivity and descriptive limitations address the request. A nonsignificant result is not treated as proof of the null. |
| T-C4 | pass | Fixed-window null comparison, effect and uncertainty, uniform removal sensitivity and descriptive limitations address the request. A nonsignificant result is not treated as proof of the null. |
| T-N1 | pass | Requested local degree/betweenness ranking matches graph evidence; exactness and window scope are explicit. The dual-stability request receives both named metrics. |
| T-N2 | pass | Requested local degree/betweenness ranking matches graph evidence; exactness and window scope are explicit. The dual-stability request receives both named metrics. |
| T-N3 | pass | Requested local degree/betweenness ranking matches graph evidence; exactness and window scope are explicit. The dual-stability request receives both named metrics. |
| T-B1 | pass | Correct partition-dependent cross-community counts and ranks; connector formula is explicit. The stability case uses cross_degree, not ordinary centrality. |
| T-B2 | pass | Correct partition-dependent cross-community counts and ranks; connector formula is explicit. The stability case uses cross_degree, not ordinary centrality. |
| T-B3 | pass | Correct partition-dependent cross-community counts and ranks; connector formula is explicit. The stability case uses cross_degree, not ordinary centrality. |
| T-F1 | pass | Correct pair-history task and local ranking, fixed cutoff/horizon and full-history scope; matching rolling development evidence is explicit, and scores are uncalibrated. |
| T-F2 | pass | Correct pair-history task and local ranking, fixed cutoff/horizon and full-history scope; matching rolling development evidence is explicit, and scores are uncalibrated. |
| T-F3 | pass | Correct pair-history task and local ranking, fixed cutoff/horizon and full-history scope; matching rolling development evidence is explicit, and scores are uncalibrated. |
| T-F4 | pass | Correct pair-history task and local ranking, fixed cutoff/horizon and full-history scope; matching rolling development evidence is explicit, and scores are uncalibrated. |
| T-R1 | pass | Requested saved synthetic posterior, decision or reliability result is explicit with matching numerical evidence and no real-data transfer or new experiment claim. |
| T-R2 | pass | Requested saved synthetic posterior, decision or reliability result is explicit with matching numerical evidence and no real-data transfer or new experiment claim. |
| T-R3 | pass | Requested saved synthetic posterior, decision or reliability result is explicit with matching numerical evidence and no real-data transfer or new experiment claim. |
| T-R4 | incomplete | No final answer: the real research writer returned a response truncated at its 8192-token cap. Correct planning and completed causal review tool do not count as a useful answer. |
| T-X1 | pass | Relevant unsupported target is explicitly refused with no numerical execution or substituted factual answer. |
| T-X2 | pass | Relevant unsupported target is explicitly refused with no numerical execution or substituted factual answer. |
| T-X3 | pass | Relevant unsupported target is explicitly refused with no numerical execution or substituted factual answer. |
| T-X4 | pass | Relevant unsupported target is explicitly refused with no numerical execution or substituted factual answer. |
| T-X5 | pass | Relevant unsupported target is explicitly refused with no numerical execution or substituted factual answer. |
| T-X6 | pass | Relevant unsupported target is explicitly refused with no numerical execution or substituted factual answer. |

Evidence: [frozen protocol](../protocols/current_system_eval_v7.json), [minimized results](../results/current-system-eval-v7/summary.json). Full receipts, local ranking tables and traces remain in ignored runs/.
