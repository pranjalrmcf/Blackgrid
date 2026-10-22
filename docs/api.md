# BLACKGRID API v1

Phase 3 service-client API. The original `blackgrid console` command remains available; Compose serves the API. It reuses the existing CLI, graph validation and workflow engine. Configured first-window community investigations run in mock mode by default; authorized clients may explicitly request the existing live OpenRouter workflow within retained limits. User datasets/uploads, arbitrary paths/tools and full-dataset scope remain unavailable. See [live setup, limits and test command](api_live.md).

## Local setup

Run from the repository in a terminal with the locked environment installed:

```powershell
.\.venv\Scripts\python.exe scripts\create_api_client.py --subject alice
$env:BLACKGRID_API_CREDENTIALS_FILE = (Resolve-Path .secrets\clients.json).Path
$env:BLACKGRID_PORT = '8766'
.\.venv\Scripts\python.exe -m blackgrid.operations api
```

The provisioning command writes a random 256-bit bearer token to `.secrets/alice.token`, and its SHA-256 digest plus subject to `.secrets/clients.json`. Neither token nor digest is logged. Both files are ignored by Git and excluded from Docker builds. Use an OS-restricted private directory; POSIX files use mode 0600. On Windows, restrict that directory's ACL to the service/operator account. Never paste credentials into prompts, screenshots or logs. Provisioning is single-operator/serialized, not an account service.

From a second local PowerShell terminal:

```powershell
$headers = @{ Authorization = 'Bearer ' + (Get-Content -Raw .secrets\alice.token).Trim(); 'Idempotency-Key' = 'trial-001' }
$job = Invoke-RestMethod http://127.0.0.1:8766/api/v1/jobs -Method Post -ContentType application/json -Headers $headers -Body '{}'
Invoke-RestMethod "http://127.0.0.1:8766/api/v1/jobs/$($job.job_id)" -Headers $headers
```

Use another idempotency key for a new job. Do not print the headers. The operator-reviewed dataset/config must pass the same checksum, rights, scope and resource checks as the CLI. A changed or missing file fails safely. First-window limits are 1,000 nodes, 10,000 edges, one job, existing 60-second tool boundaries and 2 GiB workflow memory budget. Container cgroup limits enforce the overall memory/CPU/process ceiling; a host subprocess alone does not provide OS isolation. Only trusted fixed CLI arguments execute.

## Routes and contract

All job, artifact and schema routes require `Authorization: Bearer <token>`. Health routes are unauthenticated and expose stable status/failure codes only. API docs UIs and legacy console routes are absent from this listener.

| Method and route | Contract |
|---|---|
| `POST /api/v1/jobs` | Required `Idempotency-Key` (1–64 ASCII letters/digits/underscore/hyphen). JSON object: optional `mode: mock or live`, `scope: first_window`, `condition: validated or tool_only`, `question: 1–500 characters`. Live requires `allow_paid: true` and retained operator authorization for the authenticated subject. Unknown fields rejected. New acceptance 202, replay 200, changed body under same owner/key 409. |
| `GET /api/v1/jobs/{job_id}` | Owner-only ID, state, UTC creation, mode, cancel flag, stable error code and progress (workflow stage, LLM operation count, recorded cost and held reservation). Other owner/nonexistent IDs both return 404. |
| `POST /api/v1/jobs/{job_id}/cancel` | Owner-only, JSON `{}`. Requests cooperative cancellation at an existing workflow boundary; terminal calls are harmless. Cancellation is not immediate during input parsing/native work. |
| `GET /api/v1/jobs/{job_id}/results` | Owner-only aggregate summary after completed work; otherwise 409. No raw node/event IDs, paths, prompts, private receipts or trace bodies. |
| `GET /api/v1/jobs/{job_id}/artifacts/summary.json` | Same minimized summary as a JSON attachment. Every other filename/path is rejected. No filesystem download endpoint. |
| `GET /api/v1/openapi.json` | Authenticated generated v1 schemas. |
| `GET /health/live` | Process liveness. |
| `GET /health/ready` | Existing offline configuration/data/state checks; 503 on failure. |

Errors have `{"error":{"code":"stable_code","request_id":"server-generated-id"}}`. Responses include `X-Request-ID`, no-store/nosniff/frame protection and restrictive CSP. Raw validation values and exceptions are never returned. Bodies are bounded to 4,096 bytes before JSON parsing, with a five-second read timeout. POST requires JSON and a single valid Content-Length; chunked/malformed framing is rejected. Origin-bearing browser requests are rejected; no CORS permission or cookie authentication exists. GET query parameters are unsupported.

Authenticated subjects receive a 60-request burst bucket refilling at one request/second; global admission permits a 300-request burst refilling at five/second, including unauthenticated/health requests. Limits return 429/Retry-After. One numerical job is accepted at a time across owners, excess work gets 503; no unbounded queue exists. Uvicorn bounds connections to 32. Upstream TLS/proxy settings must also enforce slow-header/connection limits. Bucket state resets on service restart; stronger distributed rate controls belong to later deployment work.

## Identity, persistence and cancellation

Subjects are operator-defined service clients, not supplied in job bodies. Store API metadata at `BLACKGRID_RUNS_DIR/api/jobs.sqlite`; work lives under a digested subject namespace and generated job directory. Each job uses its own existing workflow database/checkpoints. The API never enumerates legacy shared runs. Shared operator-approved raw input is read-only; clients cannot choose a different dataset. Client isolation is enforced by the API and filesystem namespace, not separate OS accounts. Keep the state directory accessible only to the service account.

An exclusive process lease prevents two API processes sharing this API state. SQLite ownership/idempotency records survive restart. Replaying a key returns the same job even after failure or interruption; it never launches a replacement or resets a budget. Keys/metadata are retained, with a 5,000-job capacity ceiling and no automatic deletion. Jobs interrupted by process death are marked `interrupted` on startup. Phase 3 does not automatically resume these jobs; retain their evidence for the Phase 4 recovery protocol. Stop and verify processes before any operator intervention. The normal graceful stop waits up to the configured drain interval, then terminates the fixed child process; no force-unlock is exposed to clients.

Revoke a client by removing its digest from the registry and restarting. Rotate by removing the old registry entry, preserving/removing the old token file deliberately, provisioning a new token for the same subject, and restarting. Stable subject identity retains ownership. Restart also clears rate buckets; no automatic token expiry or federation is provided. Use a real identity provider/mTLS for untrusted or high-value clients before expanding the offline boundary.

## Transport and containers

The default bind is `127.0.0.1`; `BLACKGRID_PORT` selects the port. `BLACKGRID_API_ALLOWED_HOSTS` is an explicit comma-separated hostname allowlist (default `127.0.0.1,localhost`). Wildcards are rejected. Forwarded headers are not trusted and the console must never be publicly proxied.

For direct TLS set `BLACKGRID_API_TLS_CERTFILE` and `BLACKGRID_API_TLS_KEYFILE` to operator-provided read-only files. Both are required together. `BLACKGRID_API_HOST=0.0.0.0` requires TLS configuration; use a certificate valid for an explicitly allowed hostname. HSTS is emitted on HTTPS responses. Certificate acquisition, public exposure and cloud deployment are separate operator actions. A production reverse proxy may terminate TLS only if its upstream is isolated loopback/private IPC, restricts host headers and connection/body limits, and the API is inaccessible directly. The application never trusts client-supplied forwarding headers to infer security.

The existing Compose service now starts the API from `blackgrid:phase3`, using the same state volume and resource/filesystem restrictions. It publishes only `https://localhost:8765` and mounts the digest registry, local certificate and private key read-only under `/run/secrets/`. Client tokens remain on the host. See [one-time provisioning and normal Compose commands](deployment.md). Public access is not provisioned.

The API server uses a normal Docker bridge for localhost ingress. Before importing the trusted CLI, its Linux worker wrapper installs a seccomp filter denying socket creation, connect and io_uring; descendants inherit it. It fails closed on unsupported Linux architectures/filter errors. Mock workers have no provider connection; authorized live workers use only the restricted inherited broker connection described in [live API documentation](api_live.md). This is not a general sandbox; jobs remain allowlisted and bounded. Host development on Windows remains trusted-tools-only; live API workers require the Linux deployment.

## Compatibility and references

v1 preserves field meanings and HTTP statuses; incompatible semantics require a new version. Additive fields may be introduced. Existing CLI/console behavior is retained, and numerical results are checked through regression tests. No scheduler, distributed worker, database service or LLM behavior change was added. Live access adapts the existing authorized workflow; it is not an unrestricted model endpoint.

Security rationale follows [OWASP REST security](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html), [FastAPI bearer security](https://fastapi.tiangolo.com/tutorial/security/) and [Uvicorn transport/resource settings](https://uvicorn.dev/settings/). The local console's basic HTTP server is retained only in its original trusted loopback role; [Python documents its production limitations](https://docs.python.org/3.11/library/http.server.html).
