# BLACKGRID — Sprint 2 workflow specification (wf-v1)

Written in Session 1 (2026-10-18), before implementation. This file defines what the workflow must guarantee. `SPRINT_02.md` is the plan; this file is the contract the code and tests are checked against. The scientific protocol (`sprint01_experiment.md`, exp-v1.1) is unchanged.

## 1. Run outcomes (`RunStatus`)

| Status | Meaning | Resumable? |
|---|---|---|
| `completed` | Every required analysis produced, artifacts hash-verified, report checks passed. A refused task is `completed` with verdict `rejected`. | no |
| `partial` | Finished, but a required analysis is missing or failed; the question is only partly answered. | no |
| `abstained` | Scientific abstention: a preregistered suitability rule failed. | no |
| `failed` | Tool, provider, schema, or integrity failure. | no |
| `budget_exhausted` | A cap would be exceeded, or a charge breached its reservation. | no |
| `paused` | Waiting for a person: authorization, or reconciliation of an uncertain paid call. | **yes** |
| `denied` | A person refused the requested authorization. | no |
| `cancelled` | A person cancelled at a safe boundary. | no |

## 2. Completion obligations

These come from the protocol, not from whatever the planner requested.

- **Task `community_structure_vs_null`:** requires `community_test` and `edge_removal_sensitivity`.
- **A required analysis counts as done only when all three hold:**
  - its operation is `succeeded`;
  - its artifact exists;
  - the artifact's SHA-256 equals the hash recorded when the operation finished.

  An existing file alone is not proof.
- **Refusals** (verdict `rejected`) carry no analysis obligation.
- **Scientific abstention** (verdict `abstain`) ends as `abstained`, not `partial`.

## 3. Operation states (durable, SQLite)

| State | Meaning | Resume rule |
|---|---|---|
| `prepared` | Validated and budget reserved; not dispatched. | Safe to dispatch (dispatch is marked before any request leaves). |
| `dispatched` | A request may have reached the provider. | Reuse a durable receipt if present; otherwise **pause for reconciliation**. Never resend automatically. |
| `succeeded` | Receipt or artifact saved atomically; usage committed. | Reuse the saved result. Never repeat. |
| `failed_known` | Known failure with a classified retry category. | Retry only if policy allows, under the same persisted caps. |
| `billing_unknown` | Outcome or charge uncertain (after reconciliation, or a provider error after dispatch). | Full reservation stays charged. A retry happens only within the caps. |

- **Operation ID:** `sha256(run_id | kind | role-or-tool | call index | attempt | input hash)`.
- **Retry categories:**
  - `transient`: network or timeout. One retry.
  - `malformed`: unparseable or truncated reply that was received and billed. One retry.
  - `permanent`: authentication, unknown model, or invalid request (HTTP 400, 401, 403, 404). No retry.
  - `uncertain`: dispatched, no receipt. Reconcile first.

## 4. State record

Each checkpoint stores only the following:

- run identity: run, thread, and workflow version;
- the current stage and status;
- input identities: the sanitized question, an input reference to reload from (config plus data root, or a dev case ID), and hashes of config, spec, and projection;
- versions: model, prompt, and critic;
- analyses: required, planned, completed, missing, and failed;
- references to artifacts and their hashes;
- claims and their accept/reject decisions;
- the revision count;
- the authorization scope;
- the pause reason, cancellation flag, and error category.

It never stores credentials, provider objects, connections, raw events, identifiers, graphs, generator truth, or answer keys. The graph is reloaded from its source on every resume, and its projection hash must match.

**A resume is blocked** when any of these changed or failed: the workflow version, the config hash, the spec hash, the projection hash, the model, or an artifact hash. A deliberate change starts a new run with `parent_run`.

## 5. Budget durability

Calls, tokens, retries, revisions, reservations, and charges are stored per operation in SQLite and summed from there before every reservation. Nothing is held only in memory.

There are three money caps, all hard under D-039's stated assumptions:

- the per-investigation cap;
- the project-wide total, which includes Sprint 1 spend;
- a **Sprint 2 cap of USD 1.00**, counting spend since Sprint 2 began.

One active worker per run is enforced by a lock row. A second, concurrent resume is rejected. A lock left behind by a crashed process can be taken over only with `--force-unlock`, or once its heartbeat is stale.

## 6. Authorization

- **Mock and replay** runs need no authorization. Replay never falls back to live calls.
- **Live** runs need a stored authorization scope covering: model, config hash, spec hash, projection hash, tool set, a cost ceiling, and an expiry.
- **The check comes first.** It runs before the planner, because the planner is itself a paid call.
- **Missing, expired, or mismatched authorization** causes a persisted pause. The person can then resume with `--allow-paid` or deny.
- **Cancellation** is checked at node boundaries. It cannot interrupt a computation or request that is already running.

## 7. Known limits (unchanged from Sprint 1)

These protections are not provided:

- SQLite is not a sandbox, and there is no OS isolation.
- The network guard is in-process.
- Tool timeouts are cooperative.
- Memory is not capped on Windows.
- Exactly-once paid execution cannot be guaranteed. A crash between dispatch and saving the receipt stays ambiguous, so it pauses for reconciliation.
