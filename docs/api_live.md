# Existing live LLM workflow through the API

Live API requests are available in the same Compose service. Mock remains the default. Questions use the existing automatic planner/controller routing across all 18 registered tools; clients do not need to choose a category. Results state the relevant observed-window, full-history forecast or saved synthetic research scope. See [the tool integration and prerequisites](api_tools.md). There is no silent fallback from live to mock.

## Make the first live call

Run from `C:\Blackgrid`:

```powershell
.\.venv\Scripts\python.exe scripts/ask_api.py --live --question "Does this network show stronger community structure than expected from node degrees, and is the conclusion robust to missing edges?"
```

The `--live` flag is explicit authorization for this paid request within the retained server limits. The client reads the local bearer token in memory, verifies the local HTTPS certificate, submits once, prints its idempotency key/job ID and watches progress. Output includes the workflow stage, LLM operation count, recorded actual cost, reserved budget and stable failure codes. The final response is the validated scientific summary, not private model reasoning or raw traces.

Omit `--live` for a mock question. To watch a known job without submitting another:

```powershell
.\.venv\Scripts\python.exe scripts/ask_api.py --job-id JOB_ID
```

If submission times out, retry the same question/options with `--idempotency-key` set to the printed key. A fresh key creates a new job and may spend again. Paused/interrupted/billing-uncertain work is not replayed automatically; inspect its retained receipts before reconciliation.

## Retained authorization and accounting

The operator setup command is `python scripts/configure_api_live.py --subject alice`. It reuses the existing grant and key; it does not grant a fresh allowance, fetch pricing or issue a provider request. Existing policy is preserved on subsequent invocations. Private `.secrets/live-policy.json` and `.secrets/openrouter-key.txt` are mounted read-only, with the same restricted directory ACL as the existing API secrets. Only the provider key is copied from the original environment source; the complete `.env` is never mounted or injected.

This installation retains the existing **USD 3 absolute project ceiling**, imports **USD 1.3869326885** of historical spend and unresolved reservations, and caps each live API job at **USD 0.15**. The available remainder is not a new grant. Model/reasoning/routing, per-call/token/retry limits and current pricing checks come from the existing live configuration/provider code.

Every new live job reserves its whole per-investigation cap in the shared API metadata transaction before launch. Duplicate requests share that reservation. Settled authoritative charges replace it; unknown/interrupted work retains it. Prior spend plus other API charges/holds are imported into each isolated workflow ledger, so a new job folder cannot reset the project ceiling. The policy/config identity is retained across restarts; changed grant configuration is rejected until deliberate ledger review/migration.

Historical accounting is a reviewed host-ledger snapshot at setup. Do not run other paid legacy host CLI sessions concurrently: coordination across independent host/legacy ledgers is not implemented. Use one API process. Phase 4 accepts up to eight waiting jobs and executes one at a time, reserving each whole live cap atomically at acceptance. Never-dispatched waiting cancellation releases that reservation; interrupted running live work remains held for operator review. See [recovery and accounting limits](production_phase4/report.md).

The JSON submission is `{"mode":"live","allow_paid":true,"question":"..."}`. The authenticated subject must be in the operator's live policy. Clients cannot select provider secrets, models, endpoints or budget ceilings. Missing authorization/exhaustion returns 403; invalid request flags return 422. Unknown pricing produces no completion dispatch and a stable `pricing_unavailable` failure. Pricing availability is confirmed afresh by the original provider before any paid request.

## Network and privacy boundary

Live workers retain the Linux seccomp network block. An inherited private socketpair forwards only provider requests to an in-process broker; it is not a new permanent service. The broker permits only OpenRouter model metadata GET and chat-completions POST for the selected model, replaces request headers using its mounted key, denies redirects and invokes the original bounded HTTP transport. The real key is not placed in worker environment variables, request bodies, prompts, logs or traces. Tool network guards still run before any broker access.

The existing OpenRouterProvider, planner/critic flow, scientific checks, cost reconciliation and uncertain-billing retry policy are reused. Numerical algorithms and frozen observation rules are unchanged. Model prompts retain the existing aggregation/minimization rules; raw local dataset identifiers/events are not added to prompts. Client authorization isolates job status/results/cancellation as before.

Startup and health make no provider calls. Implementation tests used fake pricing/completions with Docker networking disabled; the agent initiated no real live request. The user subsequently completed a live smoke with one LLM call and recorded cost USD 0.00124828. That confirms the configured path at that time, not future availability or general model quality. See [verification report](production_phase3/live_integration/report.md).
