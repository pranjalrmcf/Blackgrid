# BLACKGRID — Sprint 5: a useful, bounded research agent

**Planning date:** 18 October 2026.<br>
**Status:** offline capability implemented on 18 October 2026 following the user's implementation request. The original plan below is retained. See [the implementation report](../docs/sprint05_report.md) for executed checks, results and limitations. Real-LLM efficacy remains untested for the new workflow.<br>
**Authorization:** the user subsequently requested implementation of Sprint 5. No new paid execution was authorized or performed.

## 1. Goal and decision

Turn BLACKGRID from a mostly fixed community-analysis workflow into an assistant that can choose an appropriate investigation, use a small collection of dependable tools, inspect the results and request one justified follow-up. Make that process understandable and usable through the existing local console.

Defer graph prediction to the next capability sprint. First establish that the agent can answer different structural questions with different plans, preserve evidence and stop when its tools cannot answer. Prediction can then become a well-defined tool within that system.

The target experience is:

> “Which nodes connect different groups, and does that finding survive missing connections?”

BLACKGRID explains its interpretation, selects the relevant tools, computes the results locally, checks ranking stability and returns a cited answer with limitations. A user can inspect the plan, evidence, tool failures and resource use in the console.

This sprint remains descriptive and exploratory. It does not establish social influence, causal effects, verified social groups or prediction of future interactions.

## 2. Starting point: what already exists

The current repository includes a live LLM provider, mock/replay modes, a durable LangGraph workflow, local SQLite operation records, execution controls, a validated cache, evidence-linked reports and a local console. Build on these rather than replacing them with a new platform.

The agent-facing registry currently exposes three tools: `profile_graph`, `community_test` and `edge_removal_sensitivity`. The validator supplies the required community analyses and fixes their order. After executing its initial plan, the agent can revise prose but cannot request another analysis.

Sprint 4 progressed beyond its original planning sheet. [The decision log](../docs/decision_log.md), D-061–D-065, records:

- A real-LLM pilot on 24 synthetic cases. Without the plan validator, the model often omitted a required analysis; many runs ended partial before producing claims. This prevents a clean claim-quality comparison between arms.
- Review of 65 live claims by `Codex_AI`: 60 were supported and not misleading; five had meaning or citation problems despite correct numbers. This was AI review, not independent human ground truth.
- critic-v5 and prompts-v5, with regression checks for those five problem types. Agreement on the inspected claims is development evidence, not validation on new claims.
- A provider completion-token overrun and subsequent offline-tested reasoning bounds and larger reservations. Compliance with the revised request settings has not been established live.

These records guide the plan; they were inspected, not reproduced while writing it. Preserve the historical runs and frozen protocols.

## 3. Supported questions and tool arsenal

Use the existing simple, undirected, unweighted projection for this sprint. Declare direction, frequency and time information discarded by that projection. Keep first-week and full-dataset CollegeMsg scopes explicit and separate.

### Three question families

| Question family | Example | Minimum evidence |
|---|---|---|
| Community evidence | “Is clustering stronger than the specified randomized comparison?” | Existing community test and its required sensitivity check |
| Structural position | “Which nodes have many contacts, and which lie on shortest paths?” | Named centrality metric, node universe, normalization and component policy |
| Cross-community connections | “Which nodes connect the detected groups, and are their rankings stable?” | Recorded partition, defined bridge metric and ranking sensitivity |

Requests for “influential people” require clarification or an explicit proposed structural interpretation. Do not silently substitute centrality for influence. A confirmed structural interpretation may proceed; a request for actual causal influence must receive an understandable refusal.

### Four new tools, seven tools in total

These names are proposed interfaces, not existing commands.

| New tool | Calculation and output | Limits and interpretation |
|---|---|---|
| `community_partition` | A Louvain partition with recorded seed, resolution, restarts and partition identity | Produces a grouping for description. It does not establish statistical support or real social groups. Reuse a compatible saved partition when available. |
| `node_centrality` | Degree and normalized betweenness rankings, including ties and metric definitions | Degree measures contacts; betweenness measures shortest-path position. Declare disconnected-graph normalization. Use exact calculations on small graphs; any capped approximation requires a fixed sampling rule, seed and explicit label. |
| `community_bridge` | Cross-community degree and the fraction of each node's links going outside its assigned community | Requires a recorded partition. Define isolated-node behavior and ties. This is a partition-dependent node ranking, distinct from graph-theoretic bridge edges and articulation points. |
| `ranking_sensitivity` | Stability of a declared centrality or community-bridge ranking under a frozen edge-removal schedule | Report top-k overlap and a prespecified rank-agreement measure, with tie and disconnected-node policies. For community-bridge rankings, recompute partitions under the frozen rule; match nodes, not arbitrary community labels. |

Existing `edge_removal_sensitivity` remains the sensitivity test for the community verdict. It is not interchangeable with ranking sensitivity.

Specify schemas, formulas, prerequisite artifacts, failure outcomes and size/time caps before implementation. Prefer the current numerical dependencies. Do not add another library merely to increase the arsenal.

## 4. Give the planner meaningful, controlled choices

### A question-specific investigation contract

Replace the universal assumption that every investigation must produce a community-test report with requirements selected by question family. Preserve the old community workflow as a supported compatibility path.

The structured plan must record:

- The interpreted question and supported question family.
- Dataset, projection and scope identity.
- Selected tools, validated arguments, prerequisite dependencies and expected evidence.
- Why each tool is necessary for this question.
- Whether the run is exploratory or follows a frozen confirmatory procedure.
- Maximum tool/model calls, permitted follow-up and stopping conditions.

The LLM proposes a plan; trusted code checks it. A centrality-only question must not automatically incur community-null calculations. Unsupported questions produce clarification or refusal rather than a plausible but unrelated report.

### One results-driven follow-up

The new path is:

`question → interpretation → validated plan → tools → inspect results → optional follow-up → checked answer`

After the initial tools, the LLM can choose `answer`, `request_follow_up` or `abstain`, giving an evidence-linked reason. At most one follow-up round is allowed, with at most two additional tool calls and no more than six tool invocations overall. These limits are subordinate to stricter run limits.

Permitted example: inspect a bridge ranking, then request the registered ranking-stability check. If robustness was part of the original question, that check is required evidence rather than an optional embellishment.

Reject duplicate computations, incompatible scopes, unsupported tools, invalid arguments, missing prerequisites and attempts to inspect evaluator-only material. Cache reuse must retain its computation identity and provenance.

The agent cannot change a frozen hypothesis, graph window, significance threshold, metric or removal schedule after seeing the result. Exploratory follow-ups remain visibly exploratory, and every attempt is recorded. No repeated testing until significance appears.

## 5. Evidence and review must expand with the tools

A community verdict cannot serve as the approval context for all new claims. Define evidence requirements by claim type: numerical profile, centrality rank, community membership, bridge ranking, ranking stability and inferential community comparison.

1. Introduce typed result references for node ranks, partitions and comparisons. Verify that a cited metric, node reference, scope and value agree. Check ties before claiming a unique winner.
2. Separate facts established by a saved output from interpretations that require assumptions. “Highest betweenness” does not establish “most influential,” and a high score does not establish a large practical effect.
3. Support literal comparisons with the quantities being compared. Inferential wording also needs the applicable test evidence. Preserve critic-v5 controls and correct negative or qualified statements.
4. Unknown free prose must be marked unassessed or sent for review; absence of a triggered rule is not verification. Prefer structured claims with readable rendering for dependable numerical statements.
5. Keep the evaluator independent of critic decisions. Freeze a rubric extension before fresh evaluation and retain disagreements and reviewer identity.
6. Label ranking-removal results as sensitivity under assumed missingness. They are neither confidence intervals nor Bayesian probabilities and do not recover hidden truth.

Node identifiers and individual rankings stay local. External model prompts receive aggregates and minimized claim structures without raw IDs, raw event records or node-level personal profiles. Trusted local rendering can attach authorized node references to verified structured results; it must not present that rendering as an LLM-generated individual judgment.

## 6. Make the existing console a usable investigation workspace

Extend the current local console and CLI, sharing the same workflow. No new frontend framework, hosted service or database is needed.

The console should provide:

- **Question entry:** a free-text question plus three example questions matching the supported families. Show dataset, projection, scope and mock/replay/live mode explicitly.
- **Interpretation and plan:** show what BLACKGRID will answer, selected metrics, necessary tools and limits. Offer clarification when needed. Do not make routine safe execution depend on an extra confirmation screen.
- **Visible progress:** show planned, running, completed, cached, failed and skipped steps, including the reason for a follow-up. Keep elapsed time, actual/reserved resources and stop reasons understandable.
- **Useful results:** a local sortable ranking table, named metric definitions, component/partition context, a suitable network view and ranking-sensitivity results. Specify sampling or view caps for larger graphs. Graph layout must not imply significance or influence.
- **Evidence inspection:** selecting a claim reveals its result values, source artifact, scope, checks and qualifications. Distinguish a checked fact from an unassessed sentence.
- **Run history:** inspect and compare two compatible runs without merging incompatible scopes or implying that a parameter change proves an effect. Export the existing report and structured evidence.
- **Recovery:** preserve pause, resume, cancel and paid-call reconciliation. Failed or partial runs remain visible and retain completed evidence.

Mock results must be visibly labeled. The console continues to avoid starting or approving paid calls; keep paid authorization on the existing explicit path. A polished page must never imply a capability that has not run.

## 7. Work sessions and acceptance gates

These are ordered work packages, not measured time commitments. Finish the first complete question path before broadening.

| Session | Work | Acceptance evidence |
|---|---|---|
| 1. Freeze scope and contracts | Record current revision; specify the three question families, metric semantics, tool contracts, privacy boundary and budgets; define development fixtures | Written protocol and testable contracts; no implicit community-test requirement for unrelated questions |
| 2. First useful vertical slice | Implement `node_centrality`, question-specific routing and evidence-linked local reporting | One offline “many contacts versus shortest-path position” investigation; independent checks on tiny graphs; invalid metric/scope rejected |
| 3. Partitions and bridges | Add partition and cross-community tools with provenance and prerequisites | Known partition fixtures verify cross-community counts, ratios, ties and isolated-node behavior; descriptive scope is explicit |
| 4. Stability and follow-up | Add ranking sensitivity and one bounded re-planning round | A scripted provider requests a justified follow-up from actual tool evidence; duplicate requests, excess calls and scope changes stop clearly |
| 5. Claim checking | Add typed evidence bindings, rubric extension and independent evaluator coverage | Wrong node, metric, rank, partition, scope and unsupported influence claims are detected; valid qualifications remain expressible |
| 6. Console integration | Add question entry, plan/progress view, ranking results, evidence inspection and compatible-run comparison | Exercise all three question families through the real local workflow, including a failure and a resumed run; inspect the rendered interface |
| 7. Frozen evaluation | Freeze fresh graph instances, questions, scoring, prompts and budgets before generation/execution | Every attempt recorded; numerical correctness, tool selection, answer quality and resource use reported separately |
| 8. Reproduction and close-out | Reproduce offline from locked dependencies; verify compatibility; write report and next-sprint decision | Complete offline investigation in a clean environment; historical scopes preserved; limitations and unfinished gates explicit |

If time is limited, finish Sessions 1–2 as a usable increment and report the remainder as incomplete. Do not replace missing functionality with static example results.

## 8. Evaluation: prove usefulness rather than just more activity

Use separate development and fresh evaluation instances. Old Sprint 3/4 graphs and the 65 reviewed live claims are development/regression material. Keep generator truth, answer keys and future test results inaccessible to the planner and critic.

Use tiny known-answer graphs to establish numerical correctness: stars, paths, disconnected components, ties, isolated nodes and two supplied groups with known cross-group links. A fixture with a supplied partition tests the bridge formula separately from Louvain's partition choices. Do not assume a heuristic optimizer must recover planted labels.

For the frozen comparison, use the same question/graph inputs and equal maximum resource budgets across:

1. A deterministic question router and report baseline.
2. An LLM that selects one plan without a follow-up round.
3. An LLM with the bounded follow-up workflow.

Keep the numerical tools, safety checks and answer-review policy the same across these three arms so the comparison measures planning. A separate critic ablation can follow later under its own protocol.

Report appropriate tool selection, prerequisite violations, unnecessary/duplicate calls, complete useful answers, supported and unassessed claims, missed required facts, correct clarifications/refusals, failures, wall time, model calls, tokens and cost. Report the share of questions fully answered alongside unsupported-claim rate; silence must not look like success.

Use paired graph-level comparisons and disclose repeated questions on the same graph as dependent observations. Freeze the case mix, scoring and engineering acceptance thresholds before execution; justify any scientific improvement margin using pilot variability. Fresh seeds do not establish generalization to unseen graph families.

Mock/replay runs validate execution and reproducibility. Establishing benefit from real-LLM planning requires a separately authorized live comparison. If it ties or loses to the deterministic baseline, report that outcome and retain the simpler route where appropriate. Human review is preferable for a declared subset; AI-only judgments must be labeled and cannot establish independent human validation.

## 9. Resource, privacy and compatibility boundaries

- Offline mock mode remains the default. This document grants no new API or cloud allowance and does not renew the completed Sprint 4 pilot's one-run authorization.
- Preserve the existing 16,000 requested completion-token maximum, 100,000-token run ceiling, eight-call ceiling, revision limits and stricter configured monetary limits unless explicitly superseded. A follow-up must fit inside these totals, not receive an extra budget.
- Retain reasoning bounds and the current 3× completion reservation policy. Reserve against the expanded call plan before dispatch; eight nominal calls may not fit the token budget. An observed overshoot factor is not a provider guarantee. Unknown pricing or a reservation breach stops paid execution.
- Before any live trial, freeze its protocol, verify current pricing, reconcile cumulative spend and use a realistic stopping reserve. Do not reuse the old pilot's threshold, which predates larger reservations. Never reset historical spending by renaming the sprint.
- Bound numerical work, approximation size, top-k, artifact size and output volume. Tools execute trusted registered code only, with existing cancellation and ownership protections. A subprocess is not a security sandbox.
- Preserve raw CollegeMsg files, duplicates, usage decisions and graph-construction rules. No new dataset, private career data or external tracing upload is in scope.
- Record data/scope hashes, tools, seeds, parameters, prompts, provider/model identity, source revision, costs and failure status. Version changed contracts and reject incompatible resume states clearly.

## 10. Definition of done and next sprint

Sprint 5 is complete when all three question families work through the same CLI/console workflow, plans differ appropriately by question, all four new tools meet their numerical contracts, one follow-up can execute safely, and every reported factual claim has checked evidence or an explicit unassessed status.

The deliverables are the extended tool registry, question-specific investigation contracts, bounded planning loop, evidence/review updates, usable local console, frozen evaluation artifacts, reproduction instructions and a close-out report. Completion requires executed focused checks and one clean offline reproduction; this plan itself is no evidence that those checks passed.

Distinguish two outcomes in that report: **the system can execute these investigations** and **adaptive LLM planning improves useful answers**. The first is an engineering gate; the second requires the matched real-model evidence. Do not claim the second from mock success or UI completeness.

The next candidate is a narrow temporal link-prediction sprint: define the prediction horizon and candidate pairs, use time-respecting train/validation/test splits, prevent future-edge leakage and compare simple heuristics before learned models. Start it after the tool/planning interfaces are stable, with any remaining reliability limitations disclosed. A GNN is a later decision justified by baseline results.
