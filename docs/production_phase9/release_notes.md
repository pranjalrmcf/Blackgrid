# 1.0.0 — 23 October 2026

Restricted single-host operational release, cumulative production phases 1–9.

- Preserves 18 allowlisted analytical tools, agent planning, scientific validation, artifacts, resume and cost limits.
- Packages the authenticated TLS API, ownership/idempotency, durable bounded scheduling, cancellation/recovery, live cost broker and operator dashboard.
- Includes verified deterministic graph-tool caching, telemetry, resource/log limits and offline snapshot/restore controls.
- Adds GitHub build/test/security workflows, local evidence-based promotion, version/compatibility checks, rollback verification and an operations handbook.
- Sets package/application version to 1.0.0. API routes remain `/api/v1`; response version is unchanged. No Phase 9 database migration, model/prompt change or new scientific method is introduced.

Quality tooling is isolated in the locked `quality` dependency group and verification image. Production dependency versions remain unchanged. Existing saved reports and historical negative results are retained. Scientific/agent capability claims remain bounded by their original evidence; release engineering does not establish generalization, identified causality or novel research efficacy.

Public deployment, sustained real-provider SLOs, multi-host execution, external paging, managed cloud deployment, signed registry publication and vLLM are not included. See [readiness](report.md) for residual security findings and exact validation status.
