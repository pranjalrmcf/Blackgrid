# Existing-service API integration

22 October 2026. The user authorized including the Phase 3 API in the existing BLACKGRID service. Compose now starts `api` from cumulative image `blackgrid:phase3`, with certificate-verified HTTPS published only at `127.0.0.1:8765`. This replaces the console process in the same Compose service; no second permanent service was added.

This report records the initial mock service integration. The user subsequently authorized the existing live LLM path; its current authorization, budget, transport controls and successful user smoke are recorded in the [live integration report](../live_integration/report.md).

## Preservation and configuration

Inspected the old healthy Phase 2 service and confirmed zero active workflows before recreation. Retained the existing `blackgrid_blackgrid-state` volume and read-only dataset. Existing shared CLI state was not reset or exposed as API-owned jobs. The image retains the CLI and console commands. The non-root UID, read-only root/data, one CPU, 2 GiB memory, 128-process ceiling, dropped capabilities and no-new-privileges remain enabled.

Created a local `alice` service client and a 90-day localhost/127.0.0.1 certificate. Restricted the Windows `.secrets` directory ACL to its operator and SYSTEM. Plaintext client token remains on the host; the registry, server certificate and private key are mounted read-only. No credential values were printed or placed in source, build arguments, image layers or reports. `.secrets` is ignored by Git and excluded by the build allowlist. Use the certificate explicitly as client trust material; no global trust-store modification or TLS verification bypass was made.

The first internal-only bridge attempt stayed healthy inside the container but failed host connectivity: requested HostConfig bindings existed, while actual NetworkSettings port bindings were empty and the host connection was refused. This engine does not publish ports for a container attached exclusively to an internal bridge. Recorded this failure rather than treating internal readiness as host reachability.

Resolved it with a normal Docker bridge for API ingress and a narrow Linux worker entry point that installs a kernel seccomp filter before importing the existing CLI. The filter denies socket creation, connect and io_uring, is inherited by descendants, and fails closed on unsupported Linux architectures/install errors. The parent API/health client keeps networking; workers cannot create network sockets. Only fixed, validated mock CLI arguments execute. This is one containment control, not a general arbitrary-code sandbox. Linux x86-64 was exercised; the aarch64 mapping is implemented but not executed on this machine. Windows host development remains trusted-tools-only.

Recreated only BLACKGRID and its network with `docker compose down` without volume deletion, then `docker compose up -d --no-build --wait`. The original state volume identity was rechecked. Updated health probing to validate TLS certificates and hostname when the API certificate is configured; the original HTTP console probe remains supported.

## Verification

- Updated production image built through normal Compose commands (`build.log`).
- Windows API/console/deployment checks: **55 passed, 1 skipped in 15.15 seconds** (`windows_focused.log`).
- Linux focused API/console/deployment checks: **57 passed in 14.52 seconds**, including the symlink case and kernel socket denial (`linux_focused.log`).
- Running-service acceptance: **passed** (`verification.json`, `service_checks.log`). Inspected actual localhost publication, non-root controls, retained volume and read-only secret/data mounts. Verified HTTPS/HSTS, unauthenticated 401, authenticated schema access, duplicate replay, conflicting-key 409 and allowlisted artifact access.
- A full offline job completed through the service. Its minimized numerical summary matched the prior current-source host reference exactly, with one mock call and USD 0. The descriptive scientific verdict remained `not_supported`; deployment does not alter that finding or establish generalization.
- Restarted the service after that completed job; job identity, results, idempotency and readiness survived. Service remained running and healthy afterwards.

The full Linux regression passed: **576 passed in 226.60 seconds**, zero failures/errors/skips (`container_tests.log`). This includes the actual network-denied worker and HTTPS health cases. The exact user-facing certificate-verified curl health command returned `ready` with no failures. No paid provider, cloud resource or public/LAN endpoint was started. The API is reachable only on host loopback; legacy console/UI is not served there. Operators can continue normal `docker compose up`, `restart`, health and logs commands.

## Operation and remaining limits

See [deployment instructions](../../deployment.md) and [API contracts](../../api.md). The local certificate expires after 90 days and requires deliberate renewal. Do not publish ports on all host interfaces or mount plaintext token files into the service. The API still permits only bounded offline community jobs; Phase 4 scheduling/recovery, broader isolation, paid execution and public production deployment remain unapproved. Interrupted API jobs are not silently replayed. The old Phase 2 image is retained for rollback; preserve state and credentials during any rollback.
