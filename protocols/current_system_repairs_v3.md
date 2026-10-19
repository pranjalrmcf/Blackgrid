# Current-system repairs v3: real-provider verification

User authorizes code repair and real LLM execution, with USD 3 maximum for this repair/verification task. No mock or replay provider is permitted for execution evidence. Previous uncertain reservations remain charged conservatively; they are not retried, erased or treated as new allowance. Stop this task's dispatch after any new unknown-billing response.

Observed before repair: production source hashes equal the previous v2 repair freeze. Claude added a mock evaluation/harness and exposed keyword-routing failures; production code was not changed. Both v1 and Claude's v2 questions have been inspected and are development cases.

Acceptance criteria:
- In auto mode the real planner supplies a bounded analysis family (or the controller derives it from unambiguous registered tool calls). A keyword fallback cannot overrule a valid semantic plan. Explicit family settings remain honored; invalid/mixed tools remain rejected.
- Resolve required tools after family selection, persist that selection in the checkpoint and use it consistently in tools, critic, reports and resume. Pin any potential synthetic research evidence before planning; never accept a model-supplied path or unverified observations.
- Maintain deterministic refusal of unsupported real probabilities, causal influence, behavioral interventions, future-data access and selective-window significance fishing. Preserve clear reasons.
- Repeat-pair prediction must not replace an explicitly first-time-contact request merely because it mentions existing users.
- Execute real-provider diagnostic cases before repair, then a frozen real-provider verification set after repair. Preserve all attempts and source hashes. Scientific numerical specifications and caches remain unchanged and disclosed.
- Reserve disjoint per-case spend caps whose sum, including diagnostic caps, is <= USD 3. Use fresh provider prices, conservative reservations and durable usage receipts. Limit simultaneous provider requests to avoid recreating a 24-request burst; separate processes protect global tool socket controls. No automatic resend after uncertain billing.
- Report numerical/evidence integrity, semantic response quality, refusals, omissions, latency, known cost and unresolved reservations separately. Real synthetic-study reviews remain synthetic evidence even when their orchestrating LLM is live.
