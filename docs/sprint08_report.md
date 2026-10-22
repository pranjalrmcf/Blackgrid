# Sprint 8 implementation and development smoke check

A subsequent [full 24-question real-LLM evaluation](sprint08_system_evaluation_v1.md) recorded **22/24 strict passes**. The smoke results below remain the original one-question implementation evidence.

Implemented the authorized three-capability slice: behavioral clustering, similarity search and anomaly detection. The shared feature stage is bound to checksum-verified directed events and the exact recorded graph window. Four empty-argument allowlisted tools are integrated with family routing, controller validation, evidence templates, exact-claim criticism, artifact receipts, reports and the local console. Node rows use an aggregate allowlist before model disclosure. Graph-only caches are bypassed because they cannot distinguish event frequency or timing.

The [protocol](../protocols/sprint08_behavior_v1.md) was written before numerical or real-data execution. Defaults remained unchanged after inspecting results. The [guide](sprint08_guide.md) documents usage, methods, scope and explicit failure outcomes.

## CollegeMsg exploratory integration check

Run `20261019T141819Z-83ec03`, 19 October 2026, used the existing approved first window: **196 directed events, 104 active profiles, 137 projected pairs**. No self-events were present. The raw dataset was preserved, and local memberships/rankings are not included in the versioned aggregate receipt.

| Output | Observed aggregate |
|---|---|
| Behavioral clustering | Three clusters with 31, 62 and 11 profiles; standardized silhouette 0.477958. |
| Similarity search | 520 neighbor rows: five other profiles for each of 104 profiles. |
| Anomaly candidates | 20 candidates at the frozen robust-deviation cutoff; count-only baseline flagged zero. |
| Workflow | Completed; all four tools succeeded; six aggregate claims passed the deterministic critic. |
| Real LLM | `deepseek/deepseek-v4-flash-0731`; one planner call, 1,570 input tokens and 253 output tokens. |
| Time and cost | 6.401 seconds in the investigation receipt; USD 0.00029064 actual cost. Network/pricing startup is outside this timer. |

The real planner chose the behavioral family and all required tools. Numerical execution, default evidence summary, claim checking and reports completed. This is **one already-exposed development question**, not a held-out real-model evaluation or a new 24-question score. The initial sandbox attempt could not resolve the pricing endpoint and stopped before paid dispatch; the network-enabled invocation completed. No model-written behavioral interpretation or paid retry was used.

The 20 candidates are not validated anomalies. In this sparse window, reciprocal activity and temporal concentration can be unusual relative to the observed population without being harmful or unexpected in a broader population. The count baseline's disagreement exposes feature dependence; it does not establish that either detector is correct. Perfect cosine matches can arise from identical coarse profiles. Cluster sizes are imposed by the chosen representation and fixed clustering method, not confirmed communities.

## Verification and remaining scope

The new numerical and workflow checks cover directed-event feature arithmetic, duplicates, self-event treatment, future/end-boundary exclusion, deterministic results, independent cosine and robust-deviation calculations, known extreme activity, constant/empty-population abstention, event/projection mismatch, caps/deadline refusal, strict arguments, family separation, aggregate privacy, complete workflows and manifest evidence linkage. Offline providers are used only for regression engineering checks; the integration check above used a real LLM.

The full regression run passed **512 tests, with zero failures, errors or skips**, in **267.57 seconds**. It includes 19 new behavioral cases and the preceding 493 cases. Local receipts: `runs/sprint08-regression.log` and `runs/sprint08-regression.xml`. Console JavaScript also passed a syntax check. After final presentation wording and manifest-assertion refinements, **36 focused behavioral/console/report checks passed in 19.45 seconds**. Source fingerprints and the distinction between these runs are recorded in `runs/sprint08-verification.json`.

The browser check opened the real run, verified all three panels, and changed the local similarity selector to confirm neighbor results changed. It also exposed misleading inherited graph-projection wording in the answer view; that presentation text now distinguishes graph counts from directed-event features.

No new dataset, dependency, cloud service, model training or raw-data modification was required. The retained USD 3 total project ceiling remained in effect, including earlier spending and unresolved reservations. Local run receipts and regression logs remain under ignored `runs/`; the versioned [aggregate receipt](../results/sprint08-v1/summary.json) contains no node rows.

Scientific limitations: no real anomaly labels, no verified behavioral groups, no calibrated score probabilities, no causal effects, no temporal generalization test, fixed k and feature scale choices, dependent node observations, and sensitivity to missing observations/exposure. The next smallest scientific task is a separately frozen, blinded synthetic behavioral benchmark with multiple untouched graph-level seeds and null populations, before tuning or claiming detection/clustering performance.
