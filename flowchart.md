# BLACKGRID system flowchart

Current implemented system through the Sprint 8 repairs, based on `src/blackgrid/`. Versioned [guides and reports](docs/) describe implemented behavior; ignored local sprint plans under `sprints/` may include future work.

## Investigation from question to report

```mermaid
flowchart TD
    User["User question and selected configuration"] --> Entry{"Entry point"}
    Entry --> Console["Local browser console"]
    Entry --> CLI["CLI investigation command"]
    Console --> CLI
    CLI --> Load["Validate config, data checksum, rights and input scope"]
    Load --> Input["Build investigation input and bind trusted evidence"]
    Input --> Init["Initialize durable run and checkpoint"]
    Init --> Auth{"Execution authorized and within limits?"}
    Auth -->|No| Stop["Explicit refusal, denial, failure or budget stop"]
    Auth -->|Yes| Guard{"Unsupported scientific target?"}
    Guard -->|Yes| Refuse["Refuse with reason; no numerical tools"]
    Guard -->|No| Plan["Planner proposes family and allowlisted tool calls"]
    Plan --> Validate{"Validate family, arguments, prerequisites and obligations"}
    Validate -->|Rejected| Refuse
    Validate -->|Allowed| Execute["Bounded registered tools; verified cache where supported"]
    Execute --> Evidence{"Check required evidence and tool outcomes"}
    Evidence -->|Permitted adaptive structural follow-up| Follow["Bounded follow-up decision and registered tools"]
    Follow --> Evidence
    Evidence -->|Evidence ready or partial answer possible| Summary{"Analysis family"}
    Summary -->|Community, centrality, bridges, forecasting, behavior| Templates["Local evidence-bound factual summary"]
    Summary -->|Saved synthetic research review| Writer["Configured research writer using allowed claims"]
    Templates --> Critic{"Family-specific critic: evidence, values and scope"}
    Writer --> Critic
    Critic -->|Accepted or revision limit reached| Finalize["Determine completed, partial, abstained or failed outcome"]
    Critic -->|Rejected claims and revision budget remains| Revise["Bounded revision with explicit feedback"]
    Revise --> Critic
    Execute -->|Timeout, cancellation or resource failure| Stop
    Plan -->|Invalid or truncated response| Stop
    Stop --> Finalize
    Refuse --> Finalize
    Finalize --> Reports["Investigation JSON, evidence-linked Markdown, manifest and traces"]
    Reports --> View["Console reports, local rankings, behavioral comparisons and run status"]
```

This diagram follows the validated investigation path. Tool-only and scripted comparison modes are retained for development/evaluation and have different criticism and writing behavior. A valid refusal can be a completed answer. Missing required evidence is exposed as partial, abstained or failed rather than silently treated as success.

Live mode uses the real provider for planning. The current validated community, structural, forecast and behavioral summaries are local templates checked against evidence; they do not require an extra model rewrite. Mock mode is the default development option, and replay uses matching saved receipts. Live execution requires explicit authorization and current pricing.

## Data and registered analysis families

```mermaid
flowchart LR
    Raw["Immutable CollegeMsg event file"] --> Checks["Checksum, event validation and provenance"]
    Checks --> Window["Frozen size-only window selection"]
    Window --> Graph["Simple undirected unweighted graph"]
    Window --> Events["Directed repeated events in the exact selected window"]
    Events --> Features["Eight fixed activity, timing and reciprocity features"]
    Features --> Clusters["Standardized KMeans behavioral clusters, fixed k=3"]
    Features --> Similar["Exact cosine similarity; five neighbors per local node"]
    Features --> Unusual["Robust deviations; count-only baseline; candidate flags"]
    Clusters --> BehaviorOut["Aggregate model evidence; local membership and neighbor tables"]
    Similar --> BehaviorOut
    Unusual --> BehaviorOut
    Features --> ProfileCompare["Local side-by-side profile features"]
    Similar --> ProfileCompare
    Clusters --> GroupCompare["Same-snapshot join: population and candidate shares per cluster"]
    Unusual --> GroupCompare
    ProfileCompare --> BehaviorOut
    GroupCompare --> BehaviorOut
    Checks --> Full["Approved full temporal event history"]
    Synthetic["Synthetic generators and registered study artifacts"] --> Saved["Bound trusted synthetic evidence manifest"]

    Graph --> Community["Community test"]
    Community --> Null["Louvain or registered alternative; matching degree-preserving null"]
    Null --> CommunityOut["Modularity, null contrast, Monte Carlo p-value and component analysis"]
    Graph --> Missing["Registered uniform edge-removal sensitivity"]
    Missing --> CommunityOut

    Graph --> Centrality["Degree and normalized betweenness"]
    Centrality --> Ranks["Local node rankings"]
    Ranks --> Stability["Degree and betweenness ranking sensitivity"]

    Graph --> Partition["Descriptive community partition"]
    Partition --> Bridge["Cross-community neighbour counts and fractions"]
    Bridge --> BridgeRanks["Local bridge rankings and cross-degree sensitivity"]

    Full --> History["Fixed historical cutoff and forecast horizon"]
    History --> Tasks{"Known-node pair task"}
    Tasks --> New["New pairs: no prior observed interaction"]
    Tasks --> Repeat["Repeat pairs: prior observed interaction"]
    New --> Score["Registered heuristic or selected logistic model"]
    Repeat --> Score
    Score --> Predict["Uncalibrated scores and local top-pair ranking"]
    Historical["Frozen validation, test, rolling and external confirmation aggregates"] --> Compare["Matching task and method performance comparison"]
    Predict --> Compare

    Saved --> Reliability["Synthetic reliability audit"]
    Saved --> Belief["Synthetic Beta belief reconstruction"]
    Saved --> Decision["Saved experiment decision, utility, cost and sensitivity"]
    Saved --> Causal["Synthetic identification review; real effects may be unidentified"]
```

The first-window structural experiment and full-dataset exploratory structural analysis have separate specifications. Forecasting uses its bound temporal history, not the structural window label. Repeated events are retained in the temporal data; the static projection aggregates them into unique pairs. Unobserved pairs are not automatically true negative edges. Rankings and graph position do not establish behavioral influence, friendship or causal effects.

Research tools inspect registered synthetic evidence; they do not autonomously run new real-world experiments or turn synthetic posteriors into CollegeMsg probabilities. Predictive scores are rankings, with no claim of calibrated individual probabilities.

## Behavioral planning, comparisons and refusals

```mermaid
flowchart TD
    Question["Behavioral question"] --> Target{"Unsupported verification or causal target?"}
    Target -->|Yes| Refuse["Explicit refusal; no positive findings"]
    Target -->|No| Plan["Real planner selects requested behavioral tools"]
    Plan -->|Chooses tools| Validate["Validate allowlist, empty arguments, obligations and exclusions"]
    Plan -->|Refuses target| Refuse
    Validate -->|Rejected| Refuse
    Validate -->|Allowed| Limits{"Selected graph within 1,000 nodes and 10,000 pairs?"}
    Limits -->|No| Size["Pre-tool refusal: selected size, limits and first-window alternative"]
    Limits -->|Yes| Required["Every validated planned analysis becomes required evidence"]
    Required --> Events["Checksum-verified directed events in the recorded half-open window"]
    Events --> Features["Eight fixed features; repeated events kept; selected-event cap 100,000"]
    Features --> Dispatch{"Execute only selected analyses"}
    Dispatch --> Cluster["Standardized KMeans, k=3"]
    Dispatch --> Similar["Cosine search: five other profiles per node"]
    Dispatch --> Anomaly["Robust deviation candidates and count-only baseline"]
    Features --> LocalFeatures["Local reference and neighbor feature comparison"]
    Similar --> LocalFeatures
    Cluster --> Join["When both requested: verify snapshot and population, then join"]
    Anomaly --> Join
    Join --> Aggregates["Per-cluster population, candidate and baseline counts/shares"]
    Join --> LocalRows["Local anomaly ranking with cluster membership"]
    Cluster --> Artifacts["Verified tool artifacts and outcomes"]
    Similar --> Artifacts
    Anomaly --> Artifacts
    Aggregates --> Artifacts
    Artifacts --> Complete{"Every required analysis succeeded?"}
    Complete -->|Missing or unsuitable| Partial["Partial answer, failure or explicit abstention"]
    Complete -->|Yes| Public["Aggregate evidence allowlist; node rows excluded"]
    Public --> Claims["Exact descriptive claims and evidence/number checks"]
    Claims --> Report["Evidence-linked answer and report"]
    LocalFeatures --> UI["Behavior and similarity console tab; local inspection only"]
    LocalRows --> UI
    Aggregates --> UI
```

Grouped outlier requests require both cluster memberships and candidate flags, including the population denominators. Explicit anomaly exclusions are honored. Unknown keyword obligations do not expand a valid narrow semantic plan to every method; features alone cannot satisfy an analysis request. Snapshot/population mismatches are rejected and unsuitable populations abstain. Behavioral tools bypass the graph-only cache because event frequency and timing affect their results.

Profile comparisons expose counts, distinct contacts, reciprocity and temporal concentration locally. The joined aggregate shares are descriptive candidate fractions, not calibrated probabilities or evidence of fraud. Proof of criminal/malicious identity and causal influence are unavailable from these observations. The full CollegeMsg graph exceeds the behavioral node/pair caps, while the approved first window fits; full-scope structural analysis and temporal forecasting retain their separate contracts.

## Persistence, privacy and paid-call controls

```mermaid
flowchart TD
    Run["Workflow node"] --> Check["Check permission, cancellation, deadlines and budget"]
    Check --> Operation["Durable operation identity and state"]
    Operation --> Kind{"Operation type"}
    Kind -->|Numerical tool| Tool["Typed allowlist; trusted code; worker network denied"]
    Tool --> Cache{"Tool supports the verified cache?"}
    Cache -->|Yes| Cached["Validate cache identity and integrity"]
    Cache -->|No: behavior, forecast or saved research| Fresh["Compute or inspect bound evidence without graph-only cache"]
    Kind -->|Real model request| Price["Confirm prices and reserve conservative call cost"]
    Price --> Minimize["Only aggregate evidence; exclude raw events and local node or pair tables"]
    Minimize --> Transport["Trusted OpenRouter transport with wall-clock deadline"]
    Transport --> Response{"Durable response available?"}
    Response -->|Yes| Receipt["Save receipt, usage and billed cost"]
    Response -->|Uncertain dispatch or timeout| Pause["Pause affected call; retain reservation; no automatic resend"]
    Cached --> Persist["Operation ledger, run files and checkpoints"]
    Fresh --> Persist
    Receipt --> Persist
    Pause --> Persist
    Persist --> Resume["Resume from durable state and verified receipts"]
    Resume --> Run
    Persist --> SQLite["SQLite run and operation store plus LangGraph checkpoints"]
    Persist --> Artifacts["Per-run artifacts, hashes, status and sanitized traces"]
```

These are application controls around trusted tools, not a claim that arbitrary generated code is sandboxed. Workers execute registered implementations. Project and investigation caps include earlier spending and unresolved reservations. Source/configuration hashes and operation receipts support reproducibility; they do not make a critic's approval independent scientific validation.

## Evaluation and development loop

```mermaid
flowchart LR
    Protocol["Freeze questions, expected targets, rubric, budget and stopping rules"] --> Snapshot["Record source, configuration, protocol and evaluator hashes"]
    Snapshot --> Execute["Attempt every case once under the frozen protocol"]
    Execute --> All["Retain passes, refusals, failures, timeouts and costs"]
    All --> Numeric["Independent local numerical and artifact checks"]
    Numeric --> Semantic["Review whether the final answer addresses the requested target and scope"]
    Semantic --> Report["Publish local scorecard with category totals and limitations"]
    Report --> Repair["Separate development repairs and focused verification"]
    Repair --> Next["Freeze a new evaluation; preserve earlier outcomes"]
    Next --> Protocol
```

Fresh wording on reused graphs checks system behavior; it is not a new independent dataset or a causal comparison between software versions. Numerical correctness and answer completeness are graded separately. Earlier outcomes remain recorded after repairs.

| Evidence | Recorded result and scope |
|---|---|
| [General evaluation before Sprint 8](docs/current_system_eval_v7.md) | 23/24 strict passes; one research response truncated. |
| [Sprint 8 full evaluation](docs/sprint08_system_evaluation_v1.md) | 22/24 strict passes; all supported numerical results correct, two requested comparisons incomplete. |
| [First repair follow-up](results/sprint08-repairs-followup-v1/summary.json) | 10/12; implicit grouped comparison and fraud-proof handling exposed further gaps. |
| [Final targeted confirmation](docs/sprint08_repairs_report.md) | 12/12, including nine supported requests with exactly their required tools; development confirmation on reused data, with one case inspected before dispatch. |
| [Engineering verification](docs/current_test_status.md) | 530 full-suite passes; 71 final focused passes after the last exclusion refinement. |

HTML generation was excluded from timed evaluation workers. Actual browser checks separately verified changing the local reference profile, side-by-side feature values, grouped candidate shares and the membership column. These results do not establish real anomaly precision/recall or verified behavioral groups. The final auditor's missing-trace error for a zero-call refusal and its ledger-verified supplement are preserved in the repair report.

## Source map

| Responsibility | Main implementation |
|---|---|
| Commands and local UI | [cli.py](src/blackgrid/cli.py), [console/server.py](src/blackgrid/console/server.py), [console/data.py](src/blackgrid/console/data.py) |
| Validated configuration and experiment contracts | [contracts.py](src/blackgrid/contracts.py) |
| Dataset loading and graph projection | [data/collegemsg.py](src/blackgrid/data/collegemsg.py) |
| Orchestration and finalization | [workflow/runner.py](src/blackgrid/workflow/runner.py), [workflow/engine.py](src/blackgrid/workflow/engine.py) |
| Durable run and operation accounting | [workflow/store.py](src/blackgrid/workflow/store.py), [agent/budget.py](src/blackgrid/agent/budget.py) |
| Family selection and plan obligations | [agent/inquiry.py](src/blackgrid/agent/inquiry.py), [agent/roles.py](src/blackgrid/agent/roles.py) |
| Registered tools and scientific criticism | [agent/tools.py](src/blackgrid/agent/tools.py), [agent/critic.py](src/blackgrid/agent/critic.py) |
| Community experiments and structural metrics | [analysis/experiment.py](src/blackgrid/analysis/experiment.py), [analysis/structural.py](src/blackgrid/analysis/structural.py) |
| Behavioral features, clustering, neighbors, anomaly candidates and joined aggregates | [analysis/behavior.py](src/blackgrid/analysis/behavior.py), [console/template.html](src/blackgrid/console/template.html) |
| Temporal prediction and matching evaluation | [prediction/service.py](src/blackgrid/prediction/service.py), [prediction/rolling.py](src/blackgrid/prediction/rolling.py), [prediction/claims.py](src/blackgrid/prediction/claims.py) |
| Saved synthetic research reviews | [agent/research.py](src/blackgrid/agent/research.py), [analysis/reliability.py](src/blackgrid/analysis/reliability.py), [analysis/decisions.py](src/blackgrid/analysis/decisions.py), [analysis/causal.py](src/blackgrid/analysis/causal.py) |
| Provider integration and deadlines | [agent/providers.py](src/blackgrid/agent/providers.py), [agent/http_transport.py](src/blackgrid/agent/http_transport.py) |
| Evidence-linked reports | [agent/report.py](src/blackgrid/agent/report.py) |
| Sprint 8 live evaluation and independent audits | [evaluate_sprint08.py](scripts/evaluate_sprint08.py), [repair follow-up](scripts/evaluate_sprint08_repairs.py), [final confirmation](scripts/evaluate_sprint08_repairs_v2.py) |

## Document layout

- `sprints/`: ignored local sprint plans, including Sprint 8; implementation evidence is versioned under `docs/` and `protocols/`.
- [docs/](docs/): guides, implementation reports, repair notes and the decision log.
- [protocols/](protocols/): versioned scientific and evaluation contracts.
- `runs/`: local execution records, private rankings and reproduction artifacts; historical records remain in place.
- `results/`: minimized saved evaluation outputs.
