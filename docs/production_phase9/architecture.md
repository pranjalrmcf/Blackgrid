# Released single-host architecture

```mermaid
flowchart LR
  C[Authenticated client] --> TLS[Localhost TLS API]
  O[Operator dashboard] --> TLS
  TLS --> A[Ownership, schemas, idempotency and budgets]
  A --> J[SQLite jobs: one worker, eight queued]
  J --> W[Contained trusted workflow: no network]
  W --> P[Validated planner and allowlisted tools]
  P --> K[Owner/mode/config/code-scoped verified tool cache]
  P --> E[Numerical analysis and evidence checks]
  E --> R[Minimized result or explicit refusal]
  W --> B[Parent provider broker: explicit live opt-in]
  B --> L[Retained pricing, reservation and receipt ledger]
  J --> V[Private persistent volume: jobs, checkpoints, receipts, artifacts]
  R --> V
  J --> M[Sanitized local metrics, spans and alerts]
  M --> O
  V --> S[Offline private snapshot and verified restore]
```

The API, roles and worker controller share one service; there is no distributed queue, graph database, independent agent fleet or inference server. Workers execute trusted validated numerical tools, never model-generated shell/Python. Raw identifiers/events and generator truth stay out of external model prompts and public evidence. The parent broker is the only live transport path under retained authorization; mock startup and release tests incur no provider calls.

Release checks run in separate disposable containers. Synthetic staging/load state is distinct from production. CI has no production mounts or deploy credentials. Local promotion checks exact image/source/evidence identities and configuration before the idle-only backup/deploy/restart/rollback sequence. See [the original implementation map](../../architecture.md) for component details and [the handbook](operations.md) for operational boundaries.
