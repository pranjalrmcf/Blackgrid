# Sprint 5 offline engineering evaluation s5-v1

Frozen before generation or inspection, 18 October 2026. Exploratory, scripted providers only, USD 0. This evaluates engineering execution, not real LLM efficacy. New instances reuse graph families; no unseen-family claim follows.

Sixteen independent graphs: cases 1–4 are G(24,36), 5–8 G(32,64), 9–12 SBM(3 blocks of 8, within .5, between .03), 13–16 G(24,36). Generator seeds are 91001 + 100*(i-1); experiment seeds 101000+i. No previous validation seed ranges overlap. Stop on exact projection-hash overlap with registered development/Sprint 3/Sprint 4 cases, retaining failed attempts.

Cases 1–12 alternate centrality (odd) and bridge (even) questions. Cases divisible by three explicitly request ranking stability. Cases 13–16 ask about influence or predicting future interactions and must request clarification/refuse without tools. Each graph is one unit; questions/arms on it are dependent.

Arms: a deterministic router that preplans a ranking check, the scripted single-plan mock and the scripted adaptive mock. All share trusted tools, plan validation, claim checking, equal caps, no cache, and the same input questions. The adaptive mock requests the ranking follow-up when absent; this is scripted behavior, not learned reasoning. The deterministic router uses the same question contract; it is not an independent semantic evaluator.

Independent scoring imports neither critic nor inquiry claim builders. Verify manifest hashes, recompute degree and exact betweenness using the full NetworkX reference, verify partition coverage and cross-group degree from saved membership, check claim text/value/path bindings against the fixed descriptive vocabulary, and require correct refusal/no tool dispatch on unsupported tasks. Numerical tolerance 1e-9. Ranking sensitivity checks bounded metadata and [0,1] overlaps, not calibrated uncertainty. Separate per-run correctness from useful complete answer status.

Report every attempted arm, failures, required-tool coverage, forbidden community-test calls on structural tasks, unsupported/unassessed claims, useful complete answers, model/rule calls, tool calls, token estimates, cost and elapsed time. No unsupported-rate benefit can be claimed by dropping required facts. Engineering gate: all 48 attempts accounted for, all supported structural tasks complete with required tools and supported claims, all unsupported tasks refuse without tools, and numerical/evidence checks pass. A failure means repair and a disclosed new protocol/version or development rerun, not a hidden replacement.

Freeze source, dependencies, prompts and protocol hashes before generating graphs; recheck at completion. Save all attempts and sanitized artifacts. Clean reproduction uses a separate locked environment and the same snapshot, with tolerated differences only in paths, timestamps, IDs and timings. Live evaluation requires separate authorization and a new budgeted protocol.
