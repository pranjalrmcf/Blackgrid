# Live LLM API integration

22 October 2026. User-authorized implementation is deployed in the existing Compose service. **No real provider request was initiated by the agent during implementation.** The user subsequently completed the first live test: one LLM call, 1,634 input tokens, 401 output tokens and recorded cost USD 0.00124828. See the minimized [user-supplied smoke result](user_live_smoke.json). Corrected the earlier claim that mock-only API delivery fully preserved the existing live capability.

## Implementation and retained boundaries

Added `mode: live` with required `allow_paid: true`, plus an operator-maintained authorized-subject policy. Mock remains the default. The existing OpenRouterProvider, model/reasoning/routing settings, CLI authorization, current-price checks, workflow tool allowlist, scientific methods, prompt minimization and call-level billing/retry logic remain authoritative. The API still exposes only configured first-window community jobs; it does not expose all host CLI families or raw model reasoning.

The Linux worker keeps its kernel network block. A private inherited socketpair forwards provider requests to an in-process broker; no extra permanent service is introduced. The broker permits only the existing OpenRouter models GET/chat-completions POST, pins the configured model, injects the key only into the original HTTP child's private stdin, and denies redirects. Worker environment contains a broker placeholder instead of the real provider key. Tool network guards run before broker access. Broken/uncertain transport remains an uncertain billing outcome, not an automatic resend.

`configure_api_live.py` reused the existing retained absolute USD 3 project authorization, importing USD 1.3869326885 of historical spend/reservations. It copied only the existing provider key into the already restricted `.secrets` directory, not the full `.env`. Policy/key are read-only mounts and excluded from Git/builds. Per-job allowance remains at most USD 0.15, with the existing call/token/retry ceilings. No allowance was renewed and no historical record was reset.

New live admissions reserve the full per-job cap atomically in the shared API metadata transaction. Owner/key retries share one job/reservation. Each child ledger imports prior project spend and other API charges/holds. Completed authoritative charges replace reservations; interrupted, timed-out or billing-unknown jobs retain their cap conservatively. Persistent policy/config identity prevents a restart from silently raising the ceiling. Additional metadata columns default existing jobs to mock, preserving legacy idempotency digests and retained jobs.

Job status now includes mode, safe failure code, current workflow stage, LLM operation count, recorded actual cost and held reservation. Added `ask_api.py` to submit/watch a question using certificate-verified HTTPS, private token loading and a printed reusable idempotency key. Watching an existing job never submits another. See [live operation/test instructions](../../api_live.md).

## Executed checks

- Final focused Linux integration: **10 passed in 15.18 seconds** (`focused_tests.log`). This includes a complete live-mode workflow with synthetic graph data, fake model pricing/completions and actual seccomp worker/broker IPC; unknown-pricing failure without POST; endpoint/model/timeout rejection; header/key isolation; redirect refusal; explicit request authorization; persistent cap reservation and uncertain-charge retention. Simulated fixture costs are accounting test values, not actual charges.
- Full Linux suite with Docker networking disabled: **586 passed in 236.45 seconds**, zero failures/errors/skips (`container_tests.log`). All live HTTP behavior was replaced by offline fixtures. Existing numerical, console and mock workflows remained covered.
- The existing Compose production image built successfully (`build.log`), and its service was recreated only after confirming zero active API jobs. It retained its original state volume and became healthy.
- Certificate-validated readiness returned `ready` with no failures. The question client read the previous completed mock job and displayed stage `finalize`, one recorded mock operation and USD 0 (`client_progress_check.log`).
- Before the user's test, post-deployment ledger inspection found **one mock job, zero live jobs and API paid spend USD 0**. Startup/health did not contact a provider. The subsequent user-supplied live output showed plan → execute → finalize, completed state, no error, and release of the unused reservation. Its numerical results matched the prior mock/host reference.

During fixture development, the first reduced synthetic configuration was rejected because it attempted to customize first-window sensitivity-null counts. Corrected that fixture to retain the protocol's sensitivity-null rule; no production protocol/window or scientific threshold was changed.

## Remaining limits

The user's successful live smoke verifies this configured provider path at the time of that call, not future availability, account balance or broad model quality. Recorded cost is application/provider usage accounting, not an independently checked invoice. Unknown pricing stops before a completion request; failures surface stable codes without silently substituting mock mode. Neither synthetic integration nor one live smoke establishes model efficacy, generalization or causal validity.

Historical spend is a reviewed setup snapshot. Do not run additional paid legacy host CLI sessions concurrently: coordination across separate host/legacy ledgers remains outside this API process. Use the one-process/one-job deployment. Uncertain reservations require explicit operator reconciliation; they are not silently refunded. Broader scheduling, shared-ledger concurrency, automatic recovery and observability remain future Phase 4/5 work and were not declared complete here. Live API workers require supported Linux containment; Windows host development is not represented as equivalent live isolation.
