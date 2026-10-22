# Sprint 8 evaluation repairs

The missing comparison views, broad tool fallback and unclear size-limit outcome are repaired. Additional follow-up findings led to grouped-outlier obligations, a deterministic refusal for unverified fraud identities, and explicit anomaly-method exclusions. Numerical settings and the observation window are unchanged.

## What changed

* **Side-by-side profile comparison:** the local similarity selector now shows the reference and five retrieved profiles with actual sent/received counts, distinct recipients/senders, reciprocity, active-bin fraction and peak-bin concentration. Counts are recovered from the saved log-count features. It compares only artifacts with the same snapshot; incomplete or mismatched saved features display an unavailable message. Identifiers remain local.
* **Clusters versus anomaly candidates:** combined requests join saved memberships with candidate flags. Each cluster has a population, candidate count/share and count-only baseline count/share. Joined counts are included in exact, evidence-linked report claims; the local anomaly table includes cluster membership. Snapshot/population mismatches are rejected, and degenerate analyses retain abstentions. The aggregate shares are descriptive, not probabilities of wrongdoing or significance tests.
* **Narrow execution:** implicit requests retain the validated semantic planner's selected tools instead of defaulting to every behavioral method. Every selected analysis becomes a required completion obligation. Feature-only plans cannot masquerade as completed investigations. Explicit per-group/segment outlier requests require clustering for membership and denominators; explicit anomaly exclusions are honored.
* **Clear refusals:** oversized behavioral graphs are refused before numerical calls, with the selected node/pair count, caps and first-window alternative in the main report. Requests to prove or confirm fraud, scams or malicious identities are unavailable from these observations and are refused without substituting routine rankings. Descriptive screening without claims of wrongdoing remains available.

The additive comparison contract is `behavior-v1.1`; prompts are `prompts-v16`. Original feature definitions, fixed k=3, cosine geometry, robust-deviation scaling and cutoff remain unchanged. The repair acceptance criteria are recorded in [v1](../protocols/sprint08_repairs_v1.md) and the [follow-up extension](../protocols/sprint08_repairs_v2.md).

## Real-LLM verification

| Run | Strict result | What it establishes |
|---|---|---|
| Original Sprint 8 evaluation | **22/24**, unchanged | Original comparison omissions and unnecessary tool expansion are retained as failures/findings. |
| First repair follow-up | **10/12**, retained | Both original comparison paths work; newly exposed implicit segment and fraud-proof requests still failed. [Receipt](../results/sprint08-repairs-followup-v1/summary.json). |
| Final targeted confirmation | **12/12**: 9 supported, 3 scope boundaries | Required numerical outputs, joined counts/shares, privacy, exact requested tools and explicit refusals all verified. [Receipt](../results/sprint08-repairs-followup-v2/summary.json). |

Both follow-ups used real DeepSeek planner calls, four parallel process workers, independent numerical auditing, no paid retry and the retained absolute USD3 project ceiling. Each run took about **37 seconds**. Total repair follow-up cost was **USD 0.00681209**, across **23 real LLM calls**. The final batch used 11 calls; one request was refused before model dispatch. There are no unresolved reservations from these follow-ups. Accounted project spending is **USD 1.38693269**, leaving approximately **USD 1.61306731**.

The final nine supported questions ran **exactly their required tools**, with zero extra tools. The original seven cases with unnecessary expansion are also explicit regression fixtures. Actual browser checks verified the profile comparison, changing the selected reference, the per-cluster candidate shares and the added membership column. The implicit grouped request was checked in the browser after hardening.

The final frozen auditor initially reported 11 automated passes because it unconditionally opened a trace for the zero-call deterministic refusal. That trace legitimately does not exist. The audit error is preserved; a separate local supplement verifies the refusal, zero tool calls, zero findings, zero LLM operations, zero cost and expected trace absence against both receipt and ledger. The original rubric was not changed and no paid case was rerun.

The final wording set was registered before paid execution. Its explicit negative-method case was inspected before dispatch while adding a regression, and is marked development-exposed in the [protocol](../protocols/sprint08_repairs_followup_v2.json). This is targeted development confirmation on reused CollegeMsg data, not an untouched or blinded benchmark. The original 22/24 and intermediate 10/12 scores are neither overwritten nor pooled.

## Engineering verification and limits

Focused checks cover known-answer joined counts/fractions, zero-profile exclusion, snapshot/population mismatch rejection, nonmutation of source artifacts, public aggregate privacy, implicit plan preservation, mandatory completion, explicit limits and unsupported verification targets. The comparison claims pass the existing exact-claim critic and report-number checks. Full regression: **530 passed in 300.82 seconds**; that run started before the last exclusion refinement. Final focused verification after that refinement: **71 passed in 6.28 seconds**. Execution details and local evidence are recorded in [current test status](current_test_status.md).

Raw records, old evaluation results and frozen numerical protocols are preserved. Local evidence is under `runs/sprint08-repairs-followup-v1/`, `runs/sprint08-repairs-followup-v2/` and the repair regression logs. Versioned receipts contain aggregate case outcomes, not per-node data. No dependency, external service or new dataset was added.

Remaining scientific limits are unchanged: no verified anomaly labels or behavioral-group ground truth, no calibrated individual probabilities, no identified causal effects and no demonstrated temporal transfer. A stronger detector-quality claim still requires a separately frozen behavioral benchmark; successful question answering does not establish real-world detection accuracy.
