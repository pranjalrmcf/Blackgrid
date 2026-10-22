# Current automated test status

Verified on 19 October 2026 during Sprint 8 repairs: **530 passed, 0 failed, 0 errors, 0 skips** in **300.82 seconds (5m00s)**. After the last explicit anomaly-exclusion refinement, **71 focused tests passed in 6.28 seconds**.

The complete suite includes 18 repair cases in addition to the prior 512 cases. Local execution evidence: [repair full log](../runs/sprint08-repairs-v2-regression.log), [repair JUnit results](../runs/sprint08-repairs-v2-regression.xml). That full run started before the final negative-method refinement; the 71 focused behavioral, routing and intent checks verify that last change. The intermediate repair run also passed 523 tests in 307.83 seconds. A restricted-sandbox focused attempt failed Windows atomic replacements; the same focused checks passed outside it. No tests were skipped or relaxed to obtain the results.

The [repair report](sprint08_repairs_report.md) records separate real-LLM results, including the preserved 10/12 intermediate follow-up and the final 12/12 targeted confirmation. Offline providers here test engineering contracts; they are not evidence of model quality. Historical repair and execution notes below describe the earlier 493-test revision.

## Prior repairs (493-test revision)

- Fixed a real community-summary crash when the optional secondary analysis is `None`. Direct numerical and end-to-end coverage now exercise that case.
- Retained evidence-bound summaries as the default. Added a validated `request.summary_mode` choice of `evidence` or `model` for programmatic investigation inputs. Both paths use the same existing authorization, budget, scientific tool validation and critics. Unknown policies fail before model dispatch.
- Made writer/reviser lifecycle tests explicitly choose model-written summaries, preserving their checks for dispatch, uncertain billing, receipt integrity, crash recovery, authorization expiry and revision budgets. The historical live-pilot comparison also explicitly retains model writing rather than silently changing its comparison arm. Existing recorded pilot outputs and protocols are untouched.
- Added end-to-end evidence-summary coverage that permits only the planner call, requires accepted claims, and checks the negative scientific verdict.
- Restored the causal-refusal classification flag while retaining pre-execution refusal.
- Updated three provider-contract tests to capture the current trusted HTTP boundary. They still verify parameter support, reasoning limits, upstream identity/exclusion, latency preference and price ceilings without network calls.
- Corrected an aggregate-privacy assertion that incorrectly treated the field name `history_pairs` as a pair-identifier leak. Aggregate counts are permitted; identifier tables remain local and are covered by the existing prompt/trace checks.
- Updated the default CLI call-count assertion to require exactly one planner call with evidence summaries.
- Rejected clear target substitution: pair forecasting cannot silently become structural analysis, and cross-community ranking cannot silently become ordinary centrality. This rejects an incompatible plan; it does not establish a new live success rate for the previously failed bridge question.

No tests were skipped or marked expected-failure to obtain this result. Recovery and critic tests continue to exercise actual model dispatch through instrumented offline providers. New default-path tests separately cover template behavior. Mock-provider regression checks are engineering verification, not evidence of real-model quality.

## Execution evidence and limits

Actual command, run outside the Windows sandbox because its file-replacement/local-server restrictions interfered with the initial attempt:

```powershell
.venv/Scripts/python.exe -m pytest -o addopts= -q --tb=short --junitxml=runs/full-regression-repaired.xml
```

Local evidence:

- [Complete final log](../runs/full-regression-repaired.log)
- [Final JUnit results](../runs/full-regression-repaired.xml)
- [Verification summary and source hashes](../runs/full-regression-repaired-summary.json)
- [Original failure inventory](../runs/full-regression-verification.json)

The initial sandbox-restricted attempt and intermediate focused runs remain under `runs/`; the final run held production source fixed. No paid evaluation, provider charge, raw-data modification or frozen benchmark threshold change occurred during these repairs. The earlier 23/24 real-system evaluation remains a separate historical result and has not been rescored.
