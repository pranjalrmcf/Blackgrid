# BLACKGRID — Sprint 2 report: a dependable agent workflow

Date: 2026-10-18. Plan: `SPRINT_02.md`. Contract: `protocols/sprint02_workflow.md` (wf-v1). Decisions: D-042 to D-047. Plain-English guide: `docs/workflow_guide.md`.

## What changed

- **One visible workflow.** The investigation is one LangGraph state graph:
  - initialize, then authorize, plan, validate, execute, check evidence, analyst;
  - a critic and reviser loop;
  - finalize.

  A deterministic supervisor, written as ordinary code, decides permission, budget, completion, and stopping.
- **Durable operations.** Every LLM and tool call is recorded in SQLite *before* it happens. Its record moves through prepared → dispatched → succeeded, or else failed_known or billing_unknown. On resume, saved results are reused and never repeated. An uncertain paid call pauses for a person to reconcile; it is never resent.
- **Durable budgets.** Calls, tokens, revisions, and money are always summed from the saved records, so restarts can't reset them. There is a separate USD 1 Sprint 2 cap, and Sprint 1 spend is imported into the project-wide cap. One worker per run, enforced with a lock.
- **Human control:**
  - a persisted authorization pause before the first paid call;
  - scoped, expiring approval (`--allow-paid`);
  - deny, cancel, and reconcile;
  - visible outcomes for each.
- **CLI:** `status`, `resume`, `cancel`, `deny`, and `reconcile`. Exit code 3 means paused.
- **Interactive console** (user-requested, D-046):
  - `blackgrid console` is a local live console;
  - every finished run, pilot, and the index are saved as interactive offline snapshots made from the same template.

## Completion requirements (`SPRINT_02.md` §12)

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 1 | One LangGraph workflow with inspectable planner, validation, execution, analysis, critic/revision, and finalization steps; no supervisor LLM | **Met** | `workflow/engine.py`; stage stepper in the console and in `blackgrid status` |
| 2 | Frozen science matches the reference | **Met** | CollegeMsg fingerprint identical, both cached and recomputed in a clean offline environment. Pilot 15/16 identical; the 16th is an intended change (D-044). |
| 3 | Missing or failed sensitivity is never `completed`; outcomes kept distinct | **Met** | `test_failed_required_sensitivity_is_partial_not_completed`; outcome table in wf-v1 |
| 4 | Resume in a new process; completed operations not repeated | **Met** | `test_crash_then_resume_in_a_new_process_repeats_nothing`: four crash points, call counts checked |
| 5 | Crashes before dispatch, after dispatch, after the response is saved, and during finalization; an uncertain call pauses | **Met** | same tests, plus `test_crash_after_dispatch_pauses_for_reconciliation_instead_of_resending` |
| 6 | Limits and money survive restart; concurrent resume rejected; unknown billing counted | **Met** | `test_call_cap_is_enforced_across_a_restart`, `test_concurrent_resume_is_rejected`, `test_sprint1_spend_is_imported…` |
| 7 | Denied, expired, or mismatched scope; cancellation; forged or oversized requests; answer keys; wrong-scale numbers; corrupt artifacts; invalid checkpoints | **Met** | `test_workflow.py`, `test_tools.py`, `test_agent.py`, `test_console.py` |
| 8 | No secrets, raw IDs, or answer keys in checkpoints or prompts; replay offline | **Met** | `test_checkpoints_and_prompts_hold_no_secrets…`, `test_replay_never_falls_back_to_a_live_call`, LangSmith tracing forced off |
| 9 | Run ID, stage, analyses, limits, and pause reason visible through the CLI and console | **Met** | `blackgrid status`; the console's Workflow panel. The console is a local server by explicit user request (D-046). |
| 10 | Plain-English workflow guide with a restart example; honest report | **Met** | `docs/workflow_guide.md`; this report |

## Checks actually run

- **Full test suite:** 182 passed.
- **Clean environment:**
  - setup: a fresh copy with no `.venv`, runs, cache, `.env`, or data; dependencies installed with `uv sync --frozen --offline`;
  - tests: 171 passed and 1 skipped (the skip needs the raw data, which the clean copy lacks);
  - a CollegeMsg run with `--no-cache` gave a fingerprint **identical** to the reference;
  - the whole check took 3.3 minutes.
- **CLI walkthrough:** live run without `--allow-paid` → paused at `authorize` (0 calls, $0) → `status` → `deny` → `denied`. Fully offline; the provider was never created.
- **Browser check:** the live console's index, a run's tabs, and the pilot; starting a mock run from the browser; static snapshots opened as plain files.

## Failures found during the sprint (all fixed, with tests)

1. **A revision was counted** although the call cap prevented the call.
2. **The console showed a stale stage and status**, because finalize rendered the page before publishing the final status.
3. **The console crashed for a denied run** with no pricing.
4. **Nested DOM children** rendered as text in the new console.
5. **The identity guard caught a test fixture** whose model name didn't match its config. This was correct behaviour; the fixture was fixed.
6. **The console server replied to rejected POSTs before reading their body.** On Windows this intermittently aborted the connection. It now always consumes the body (at most 4 KB) first.

## Time and cost

- **Money:** USD 0 spent in Sprint 2; no paid call was made.
- **Totals:** project total so far USD 0.0051, all from Sprint 1. Sprint 2 cap: USD 1.
- **Time:** about 1 hour of agent wall-clock time for implementation and verification. Human hours were not measured, so none are claimed.

## Limitations (unchanged or new)

- **Exactly-once paid execution is impossible to guarantee.** The ambiguous case pauses rather than guessing.
- **Cancellation is cooperative.** There is still no OS sandbox, the network guard is in-process, and memory is not capped on Windows.
- **The console is a local, single-user tool** with no user accounts. Its token protects against other web pages, not against other programs running as you.
- **Orchestration parity is not scientific improvement.** Nothing here shows that the framework improves accuracy.
- **The critic's real-model value is still untested.** The pilot remains a scripted plumbing check.

## Next smallest step

With separate authorization (USD 1 Sprint 2 ceiling): one live validated CollegeMsg investigation plus one controlled recovery case, both using `deepseek/deepseek-v4-flash-0731`. Then Sprint 3: fresh validation cases and an independent evaluation. The optional Louvain/Leiden comparison stays deferred to a new preregistered protocol.
