# Phase 3 API scope and acceptance

Authorized 22 October 2026 after deployment commit `594e91b` was pushed.

The existing console is a loopback-only operator interface with a page/session token, transient jobs, shared state, and no client identity. It is retained for trusted local use. Its routes must never be forwarded by a public proxy. The new opt-in FastAPI/Uvicorn listener exposes only versioned job routes and health; it does not mount the console or a filesystem server.

The smallest acceptance slice is an authenticated, bounded, offline community investigation against the operator-reviewed first-window config. Each client owns a separate namespace; job lookup, cancellation, results and minimized artifact download all require that owner. Persistent submission metadata makes retries idempotent across threads and service restarts. One child workflow runs at a time. Interrupted jobs are recorded and never silently replayed. Scheduling/recovery expansion remains Phase 4.

Requests cannot select paths, upload files, alter graph limits, request full-dataset scope, enable network or authorize paid calls. Existing validated RunConfig, checksum/rights checks, 1,000-node/10,000-edge limits and deterministic CLI workflow remain authoritative. Results expose aggregate scientific fingerprints, not raw identifiers/events, private traces, checkpoints or arbitrary files.

Credentials are high-entropy opaque bearer tokens represented only by SHA-256 digests in an operator-provisioned read-only file. This is service-client authentication, not an OAuth identity provider. Rotation/revocation takes effect on restart. Bound request sizes, per-client rates, global admission, safe errors and correlation IDs are tested. New dependencies are FastAPI/Uvicorn and their required transitives; existing locked package versions are preserved.

The API binds loopback by default. Non-loopback binding requires certificate/key configuration. TLS terminates in Uvicorn or an explicitly configured trusted reverse proxy; proxy headers are not trusted automatically. No public listener, paid provider, cloud service or workload benchmark is started by implementation.

Required checks: missing/wrong credentials; cross-owner reads/results/cancel/artifacts; malformed/oversize/unknown fields; traversal and symlink rejection; rate limiting; concurrent duplicate and conflicting submissions; restart idempotency; cancellation; redacted failures; tiny offline workflow integration; existing console/scientific regression; frozen lock and dependency security scan. Record actual outcomes in the completion report.
