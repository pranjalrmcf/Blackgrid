# Real LLM use and the simpler BLACKGRID console

Implemented and exercised on 18 October 2026, under the user's request to use LLMs for less than one dollar and simplify the UI.

## Delivered

The console now has a light, restrained layout, readable labels, question-led history and an answer-first result view. It explains what a score means before exposing method details. Technical run diagnostics remain available under expandable sections; evidence, activity, full reports and cost have separate tabs. Refusals and abstentions are visibly different from completed descriptive findings.

Real AI is opt-in at console startup: `uv run --frozen blackgrid console --allow-paid`. The mode selector distinguishes the live model from the scripted free demo. A retained USD 0.50 allowance is shared by this task's trials and subsequent console use. Each run is capped at USD 0.15 or the smaller remaining amount; the project ceiling includes all prior durable spending. Restarting does not reset the allowance. Browser requests cannot create a new grant. Existing pricing confirmation, 3x completion reservations, token/call limits and unknown-billing recovery remain active.

Paid console use defaults to one plan. Explicitly requested stability checks are still required. Optional follow-up can be enabled in advanced settings. Node rows remain local; the external model sees aggregate evidence and the question, not raw identifiers/events.

## What the live trials found

Model: `deepseek/deepseek-v4-flash-0731` via the existing OpenRouter adapter. Current public pricing was fetched before execution. Requested completion cap remained 16,000 with 12,000 reasoning tokens, rather than silently reducing the user's configured limits.

| Exploratory trial | Single plan | Adaptive | Accounted cost |
|---|---:|---:|---:|
| Initial frozen s5-live-v1, four independent graphs | 3/4 useful | 0/4 useful | USD 0.0093288274 |
| Fresh s5-live-v2 after repairs, two independent graphs | 2/2 useful | 2/2 useful | USD 0.0041775948 |

The initial failures remain saved. Three adaptive runs abstained because the model could not see the private node IDs. Both plans on one bridge question were rejected for requesting supplementary centrality. These were integration shortcomings, not incorrect numerical calculations.

The repair clarifies that verified individual tables are rendered locally and that the follow-up role chooses an analysis rather than naming individuals. Bridge plans may include a supplementary centrality calculation. This is prompts-v7; the numerical tools and structural claim vocabulary did not change. A separate protocol was frozen before generating the two new graphs. It also explicitly requires the facts requested, preventing a nonempty but incomplete answer from scoring useful.

All four fresh attempts completed with the required facts, zero unsupported reported claims under the fixed vocabulary and matching numerical/evidence checks. Single-plan mode used four model calls across two graphs; adaptive mode used six. This small check does not establish adaptive planning as better and motivates the cheaper single-plan console default. It is not independent human validation or a real-world error-rate guarantee.

## Actual console check and cost

A real-AI CollegeMsg first-week bridge/stability investigation was started through the new UI and completed: `runs/20261018T151142Z-fdbb5f`. It used two model calls and accounted USD 0.0020718709. Only aggregate evidence was sent externally; no individual findings are published in this report.

Across the initial trial, fresh check and console smoke test (13 live investigations), **accounted task spend is USD 0.0155782931**, leaving **USD 0.4844217069** of the retained allowance at close-out. Provider-reported cost totals USD 0.010787846; accounting is deliberately conservative. Prior project spend was USD 0.1285851756 and was not reset. These figures are a snapshot, not a promise that subsequent manual console use is free.

The client refuses calls whose reservation would exceed the most restrictive remaining cap. As documented after the earlier provider overrun, no client-side rule can guarantee a provider honors its token/pricing contract; a reservation breach stops further calls in that run and requires investigation. No reservation breach occurred in these checks.

## Verification

- Final full offline regression suite: **308 passed in 190.69 seconds**. Focused allowance/console/workflow checks passed before paid calls.
- All manifest-listed artifacts in the 13 live investigations matched their saved hashes.
- All four fresh live investigations replayed offline with identical claims, follow-up decisions and status; replay cost USD 0.
- The fresh trial has an 88-file source/config snapshot. Protocols, source hashes, attempt records, failures, timings and cost remain in the local run artifacts.
- Browser checks covered the new home page, readable result view, ranking labels, evidence inspection, real-AI mode and a real start-to-finish console action. A later UI-only navigation adjustment returns newly opened investigations to the top of the answer.

Minimized results: [summary](../results/sprint05-live/summary.json). Protocols: [initial pilot](../protocols/sprint05_live_pilot.md) and [fresh check](../protocols/sprint05_live_check_v2.md). Usage: [console guide](sprint05_guide.md).

The initial trial is closed. Running the live-check command again would consume more of the same allowance and reuse inspected cases; replay is the appropriate free reproduction path.
