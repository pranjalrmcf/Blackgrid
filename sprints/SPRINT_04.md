# BLACKGRID — Sprint 4: reliable execution and defensible claims

**Planning date:** 18 October 2026.<br>
**Status:** plan only; implementation has not started.<br>
**Authorization for this task:** review the codebase and write this Markdown file.
No code/configuration changes, new paid calls, dependency installation or broader
scientific experiments are authorized by this document.

## 1. Decision after reviewing the codebase

The current foundation is usable for a focused corrective sprint. It is **not yet
ready for unrestricted research or a new prediction/GNN extension**. Existing tests
pass, and the full-dataset path has a verified saved mock run, but targeted checks
reproduced gaps that the suite does not currently catch.

Sprint 4 should close those gaps, align claim checking with independent review, and
freeze a new evaluation on fresh cases. A successful outcome is a more trustworthy
existing investigation, not more algorithms or infrastructure.

### Review evidence

| Check performed for this plan | Result |
|---|---|
| Current source revision | `079dd02`, with uncommitted token-limit/configuration updates; the working tree was reviewed |
| Full regression suite | **218 passed in 121.69 seconds** using the existing environment |
| Targeted synthetic/in-memory probes | Five gaps reproduced; details below |
| Saved full-dataset mock run `20261018T103944Z-5673fa` | `completed`; all 12 manifest-listed artifacts matched their recorded hashes |
| Saved live run `20261018T110002Z-923f36` | `failed` on analyst truncation; all 11 manifest-listed artifacts matched hashes; 3 calls, USD 0.0027437059 recorded |
| New paid/network activity for this review | None |
| Code changes during this task | None; code/configuration/test/protocol/script hashes checked against a pre-review baseline |

The saved-run check verifies recorded integrity and outcome, not a fresh reproduction
of the approximately ten-minute full-dataset experiment. The higher live token settings
were inspected, not exercised against a paid provider. No credentials or `.env` contents
were read. This was a focused review, not an exhaustive security or statistical audit.

Local review evidence: `runs/documentation_checks/sprint4_review/probes.json` and
`runs/documentation_checks/sprint4_review_before.json`. These are ignored local artifacts.

## 2. Confirmed findings that define the sprint

### R1 — A live worker's lease can be taken over during a permitted long tool call

**Priority: P1.** [Worker locking](../src/blackgrid/workflow/store.py), `acquire`, lines
169–182, uses a 900-second stale-heartbeat threshold. Heartbeats occur around workflow
actions, rather than continuously during a long synchronous tool calculation.
The full-dataset configuration permits a 1,200-second tool call; the resource contract
also permits a higher full-scope ceiling.

The in-memory probe acquired a lease, aged its heartbeat by 901 seconds while the
owning process was still alive, and acquired another lease without `force=True`.
This reproduces the lease-takeover condition; it did **not** execute two concurrent
full-dataset jobs. The consequence is that the single-worker guarantee can fail for
an otherwise permitted long-running calculation.

**Required outcome:** normal resume cannot take over an actively executing worker
merely because a tool outlasts the heartbeat interval. Crash recovery must still work,
and an old owner must be prevented from publishing results after losing ownership.

### R2 — Accepted experiment choices do not match the numerical implementation

**Priority: P2.** [Experiment contracts](../src/blackgrid/contracts.py), lines 259–261,
accept `greedy_modularity` and `erdos_renyi_gnm`. [Tool arguments](../src/blackgrid/agent/tools.py)
also accept the greedy method. However, [the numerical analysis](../src/blackgrid/analysis/experiment.py),
lines 192–208, always uses Louvain and degree-preserving swaps.

A valid configuration and direct registered-tool request naming greedy modularity and
the Erdős–Rényi null were accepted. The probe observed **100 Louvain calls and 19
degree-swap calls**. This can make recorded method/null choices disagree with execution.
The shipped Louvain/degree-preserving configuration is the implemented combination;
the finding concerns accepted alternatives, not evidence that its existing result is wrong.

**Required outcome:** reject unimplemented combinations before execution. Adding new
implementations is not necessary to close this finding. Never silently substitute methods.

### R3 — Cached results are accepted without validating their contents

**Priority: P2.** [Cache loading](../src/blackgrid/agent/tools.py), lines 243–247, reads a JSON
payload directly. The key identifies the requested computation but does not verify
the returned payload's integrity or scientific schema.

After caching a profile for a 30-node synthetic graph, the probe changed the cached
node count to 777. A fresh tool context returned **777**, marked as a cache hit.
Later run-artifact hashes cannot establish that the original cache contents were valid
if those altered contents are adopted and hashed as new evidence.

**Required outcome:** cached data must be tied to its computation identity, checked
against recorded integrity metadata and validated before becoming evidence. Define the
behavior for corruption, malformed files, stale versions and interrupted writes.

### R4 — The critic still accepts unsupported strength language and incomplete citations

**Priority: P2.** [Claim checking](../src/blackgrid/agent/critic.py), around lines 135–144,
checks a supported verdict and comparison conditions, but does not define a threshold
for “strong” or require the cited fields to establish both sides of a comparison.

The probe reproduced acceptance of “strong community structure” with only the observed
Q cited, given a supported context. Sprint 3 independently identified eight accepted
claims with strength or citation deficiencies. The full-dataset decision log records
the same strength-language limitation.

**Required outcome:** use a versioned claim-support policy informed by blinded review.
Statistical evidence against a null does not automatically justify an effect-strength
adjective. Correct comparisons must cite the quantities being compared.

### R5 — Interrupting the suite can leave a finished record labelled running

**Priority: P2.** [Sprint 3 orchestration](../src/blackgrid/evaluation/sprint3.py), lines 113 and
224–239, initializes status as `running`, catches `Exception`, and writes the final
receipt in `finally`. A `KeyboardInterrupt` bypasses that exception handler.

The probe interrupted before case execution and found a saved `suite.json` with a
finish timestamp but `status: running`. This confirms the previously documented issue.

**Required outcome:** supported interruption/cancellation paths preserve completed
artifacts and charges, publish an accurate terminal or explicitly resumable status,
and never imply that an ended process is still executing.

## 3. Scope and boundaries

The sprint covers execution integrity, claim support, independent review and evaluation
of the existing community investigation. Preserve these separate scopes:

- The historical first-week CollegeMsg experiment and its saved results.
- The explicitly selected exploratory full-dataset experiment, `exp-v2-full`.
- Synthetic correctness fixtures, development cases and already-inspected Sprint 3 validation.
- New Sprint 4 validation cases generated only after the relevant protocol is frozen.

Do not add a GNN, graph prediction, Bayesian inference, causal estimator, new dataset,
new frontend framework, distributed workers, arbitrary generated-code execution,
cloud infrastructure or a community-method default switch during this sprint.

Do not rewrite historical reports or rubric decisions to make them appear to satisfy
new rules. Record new versions and deliberate parent-run relationships where relevant.
The already-inspected Sprint 3 cases are regression/development evidence from now on.
Sealed tests remain unopened until a separately frozen evaluation authorizes them.

## 4. Proposed work sessions

Sessions are ordered work packages, not calendar commitments or measured effort.
If time is limited, complete R1–R3 and terminal-status correctness before expanding
the evaluation. Record remaining work rather than declaring the whole sprint complete.

### Session 1 — Freeze the repair and review contracts

1. Confirm the active source revision, working-tree changes, current runtime settings
   and baseline test results before implementation.
2. Write failing regressions for R1–R5 using controlled clocks, tiny synthetic graphs,
   fake providers and temporary artifacts. No long sleep or paid call is required.
3. Define expected outcomes for live-owner contention, crashed-owner recovery, cache
   corruption, unsupported methods and suite interruption.
4. Freeze a human-review rubric for claim support, effect-strength wording, comparisons,
   missing evidence, correct qualification, refusals and unassessed prose.
5. Review the 81 blinded Sprint 3 claims; retain judgments, uncertainty and disagreements.
   Use a second reviewer where feasible. Record actual reviewer participation honestly.

**Acceptance:** failures are reproducible and the support rubric is written before
using fresh evaluation outcomes. If human review is unavailable, implementation may
continue on numerical/operational defects, but the scientific review gate stays pending.

### Session 2 — Repair ownership and interruption outcomes

1. Choose the smallest reliable lease/heartbeat design for the longest permitted tool
   and provider calls. Document its behavior when a process is alive, stalled or dead.
2. Ensure that a competing ordinary resume cannot displace an active worker. Include
   ownership checks/fencing before accepting a late result from a displaced owner.
3. Preserve a documented, deliberate crashed-worker recovery path. Do not treat elapsed
   time alone as proof that a process is dead.
4. Make suite interruption and cancellation records consistent with the actual process
   state, artifact status and any dispatched operations.
5. Recheck per-investigation cancellation so the new suite behavior does not weaken the
   existing workflow's paid-call ambiguity and reconciliation rules.

**Acceptance:** controlled-clock tests cover calls longer than 900 seconds without
actually waiting that long; only one owner may publish; recovery remains possible;
interrupted runs retain evidence and have an understandable status.

### Session 3 — Make validated requests match actual computation

1. Align experiment validation, tool schemas and execution capabilities. Prefer rejecting
   the currently unimplemented optimizer/null choices to implementing additional methods.
2. Verify that a rejected combination fails before numerical work or a paid call.
3. Check first-window/full-dataset boundaries, scope-specific resource limits and
   sensitivity-null settings across start, resume, reporting and cache identities.
4. Retain the old valid Louvain/degree-preserving behavior. If metadata/schema changes
   affect hashes, version them explicitly and distinguish semantic from byte-level parity.

**Acceptance:** the executed method and null agree with the recorded specification;
unsupported combinations cannot reach the numeric executor; the two data scopes
remain explicit and their historical results are preserved.

### Session 4 — Make cache hits trustworthy

1. Define cache metadata for computation identity, tool/implementation version, relevant
   parameters, graph identity and payload integrity.
2. Validate cached result schemas and applicable numerical invariants before reuse.
3. Write new entries safely so interruption does not leave an apparently valid partial file.
4. Define and log a policy for corrupt or stale entries: fail clearly or explicitly
   recompute under the same protocol. Preserve diagnostics; do not silently reinterpret
   an old entry or choose a different experiment based on its result.
5. Compare valid cache-hit results with uncached execution using scientific fingerprints.

**Acceptance:** altered counts, malformed JSON, wrong computation identities, stale
versions and partial writes are rejected or handled according to the documented policy.
Valid reuse preserves numerical outcomes. Hashes are integrity checks, not a claim of
security against an attacker who controls every local file and receipt.

### Session 5 — Improve claims without grading the critic with itself

1. Version the critic after inspecting the blinded-review disagreements. Preserve the
   independent evaluator and historical judgments; version any evaluator change separately.
2. Require cited quantities to establish a comparison. Distinguish a literal numerical
   comparison from an inferential claim that needs a null-test conclusion.
3. Remove unoperationalized “strong”/“real group” wording, or support it only under an
   explicitly defined, justified and prespecified interpretation and evidence requirement.
4. Check affirmative and negated claims, multiple clauses, misleading numbers, wrong
   evidence bindings and unsupported causal language. Do not rely on trigger words alone.
5. Treat unknown claim forms as unassessed or requiring review; do not automatically
   approve them because the narrow mock-language rubric has no matching rule.
6. Make tool descriptions agree with actual configured sensitivity replicates and scope.

**Acceptance:** the known unsupported forms are handled on regressions and new adversarial
fixtures, while correct qualified or negative findings remain expressible. The critic's
own acceptance is never the sole definition of ground truth.

### Session 6 — Fresh evaluation, reproduction and close-out

1. Freeze new case IDs, disjoint generator schedules, task mix, evaluation rules, budgets,
   metrics and stopping criteria before generating or inspecting their scientific results.
2. Do not reuse Sprint 3's `val-001`–`val-024` as unseen evidence. Record exact-hash overlap
   checks and any reuse of generator families/parameters; no unseen-family claim follows
   from fresh seeds alone.
3. Compare a deterministic rule baseline, tool-only mock and revised validated mock on
   matched inputs. Match maximum resources and report actual use and failures.
4. Report unsupported/assessed claims, unassessed counts, complete useful answers,
   positive-answer coverage, correct refusal, abstention, failures, time and cost.
   A lower unsupported rate obtained by omitting useful answers is not sufficient.
5. Keep graph-level units and paired comparisons. State exploratory status and any
   corrections after inspection; retain all attempts and unknown denominators explicitly.
6. Reproduce a complete offline workflow in a clean locked environment with all runtime
   assets included. Compare cached and uncached execution where applicable, and verify
   both the first-window and full-scope integration with appropriate bounded fixtures.
7. Write a sprint report, record remaining limitations, and decide whether to proceed to
   a separately authorized live pilot or another reliability iteration.

**Acceptance:** independent checks reproduce the final evidence, every attempted case
is accounted for, and operational fixes do not produce misleading scientific success.
Unexpected or unfavorable results remain valid sprint outcomes if handled honestly.

## 5. Live-model and token-budget policy

The current working tree has a 16,000-token per-call maximum, a 100,000-token per-run
ceiling and live configurations requesting a 240-second timeout, following D-056.
These differ from the original Sprint 1 defaults. Preserve that user-requested change
unless a later explicit decision supersedes it; do not silently revert it during repairs.

The currently documented money ceilings remain USD 0.50 per investigation and USD 10
project-wide, with a current-sprint ceiling of USD 1 in the existing accounting model.
The operation store still labels its current sprint `sprint2`. Before any paid Sprint 4
work, explicitly decide the sprint attribution and approved remaining ceiling while
retaining prior spend. Creating a new folder or sprint label is not authorization to
reset spend accounting. This plan sets **no new paid allowance**.

Use fake providers to verify long reasoning-token usage, truncation, retry reservations,
timeouts and the most restrictive remaining limit. The 8-call ceiling does not guarantee
that all 8 calls fit a 100,000-token budget when each reserves 16,000 output tokens.
Test that the workflow stops before an unaffordable call rather than assuming every
revision is possible.

A live pilot is optional and requires separate authorization covering model, price,
token/call/retry limits, total spend and stopping rules. Unknown pricing disables it.
The previous paid run failed on truncation; raising configuration limits alone does
not demonstrate a successful recovery. Never automatically retry that historical run.

Use dummy credentials for logging/redaction tests, including commented key lines and
exception paths. Do not read or print `.env` during review. The previously documented
credential exposure should not be repeated; any required account-side remediation
must be handled separately by the authorized account owner.

## 6. Scientific and privacy requirements

- Keep synthetic benchmark scores separate from exploratory CollegeMsg findings.
- Preserve every raw event and duplicate policy; no new dataset acquisition or private
  employee/career-data ingestion is in scope.
- Keep raw identifiers and records out of model prompts, external tracing and reports.
- Missing observations remain unknown, not confirmed non-links.
- Do not turn centrality into influence, a small p-value into effect strength, or a
  community partition into verified social groups.
- Label findings as descriptive, predictive, simulated intervention, identified causal
  or unsupported according to the available evidence. Current work remains descriptive.
- Do not retune a frozen threshold or rubric after test inspection and present the same
  cases as confirmatory evidence. Register a new version and preserve prior attempts.
- Trusted local tools, cooperative deadlines and in-process network denial are not an
  OS sandbox. Do not claim enforced memory isolation or exactly-once paid execution.

## 7. Deliverables and definition of done

| Deliverable | Completion evidence |
|---|---|
| Worker ownership repair | Active-owner, long-call, crashed-owner and fenced-publication regression results |
| Accurate interruption status | Suite and investigation records agree with cancellation/failure/resume state |
| Honest method contracts | Unsupported optimizer/null requests rejected; supported requests execute exactly as recorded |
| Validated cache | Identity/integrity/schema checks, safe writes, corruption outcomes and cache/no-cache numerical parity |
| Versioned claim policy | Human-review rubric, disagreement record, critic changes and independent evaluator versions |
| Fresh evaluation | Frozen protocol, new case registry, all-attempt ledger, independent scores and useful-answer coverage |
| Compatibility evidence | First-window and full-dataset scope checks, historical artifacts preserved, token changes documented |
| Reproduction | Clean offline end-to-end run, complete source/runtime assets, dependency identities and evidence hashes |
| Close-out report | Actual test outcomes, costs, failures, limitations, review status and next decision |

The sprint is complete only when applicable deliverables have executed evidence.
Missing human review, unresolved ownership defects or unverified reproduction remain
explicit incomplete requirements. Passing the existing 218 tests alone is insufficient
because this review reproduced behavior outside their present coverage.

No success percentage for a future real model is asserted. Any confirmatory improvement
margin, allowed discovery-recall loss or uncertainty target must be justified and frozen
before its fresh evaluation. Offline mock improvements demonstrate engineering behavior,
not real-model efficacy or publication readiness.

## 8. Immediate next action after implementation is authorized

Start with R1: write a controlled-clock regression reproducing takeover of a still-live
worker during an allowed long tool call. Fix ownership before broadening execution.
Prepare the blinded human-review activity alongside these operational repairs.

References: [Sprint 3 results](../docs/sprint03_report.md),
[full-dataset protocol](../protocols/full_dataset_experiment.md),
[decision log](../docs/decision_log.md), and
[future roadmap](../docs/FUTURE_POTENTIAL_AND_ROADMAP.md).
