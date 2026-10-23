# All registered tools through the production API

The API now passes new questions to the existing `auto` planner/controller route. Clients send their question normally through `scripts/ask_api.py` or `POST /api/v1/jobs`; no analysis-family field is required or accepted. Real live requests use the existing LLM planner. Mock requests use the existing deterministic stand-in, which tests plumbing rather than semantic model quality.

The catalog contains exactly the 18 tools in `blackgrid.agent.tools.TOOLS`. The controller still validates tool names, typed arguments, compatible analysis families, prerequisites, frozen numerical settings, budgets and privacy boundaries. A single investigation uses a compatible set of tools; arbitrary code, paths, methods, mixed incompatible plans, supplied outcomes and held-out answers remain rejected. No scientific algorithm, model, prompt template or provider policy was changed. The planner's request now says `family=auto`; token counts may differ from the earlier forced-community API even when numerical results agree.

| Family | Registered tools | Returned evidence |
|---|---|---|
| Community | `profile_graph`, `community_test`, `edge_removal_sensitivity` | Graph aggregates, modularity-versus-null result and sensitivity |
| Centrality | `node_centrality`, `ranking_sensitivity` | Degree/betweenness and ranking-stability aggregates |
| Bridges | `community_partition`, `community_bridge` | Descriptive partition and cross-community connection aggregates; ranking sensitivity is reusable |
| Behavior | `behavior_features`, `behavior_clustering`, `behavior_similarity`, `behavior_anomalies` | Directed-window profile, clustering, similarity and unusual-profile aggregates |
| Forecast | `temporal_profile`, `link_prediction`, `prediction_compare` | Fixed-cutoff history, known-node pair ranking summary and historical evaluation aggregates |
| Research | `reliability_audit`, `belief_update`, `experiment_decision`, `causal_identification_check` | Hash-verified saved synthetic calibration, Bayesian beliefs, decision and identification review |

Centrality is not influence, descriptive communities are not significance findings, unusual profiles do not establish malicious intent, and forecast scores are not calibrated probabilities. Research tools inspect the existing saved synthetic demonstration; they do not infer real CollegeMsg posterior probabilities or real causal effects. These distinctions appear in the result's scope and claim type.

## Normal use

From `C:\Blackgrid`, with the existing service running:

```powershell
.\.venv\Scripts\python.exe scripts\ask_api.py --question "Which nodes bridge separate communities, and are those rankings stable?"
```

Add `--live` to explicitly authorize a real paid LLM request within the retained grant. No new allowance is created by this integration. Other examples:

- “Which nodes have the highest degree and betweenness?”
- “Cluster behavioral profiles and find similar users and unusual activity candidates.”
- “Which pairs who have never messaged will message next month, and how reliable is the ranking?”
- “Review the saved synthetic posterior beliefs and next-experiment decision.”

The client prints tool names, analysis descriptions and states for all 18 tools. Final results add `family`, analysis-specific `scope`/`claim_type`, `analyses` with allowlisted aggregates, closed-vocabulary evidence-linked `conclusions`, and `missing_analyses`. The community `summary` fields remain compatible. Other families omit community p-values/modularity fields instead of implying a community test was run. Valid partial/abstained investigations have a readable minimized result; they are not promoted to completed work. Arbitrary model prose, drafts, prompts, raw node/pair rows, rankings and local files are not downloadable. Authenticated `GET /api/v1/capabilities` lists tools and whether prerequisite evidence is configured; execution still performs its own integrity and scientific checks.

## Isolated evidence and Docker

The cumulative image is `blackgrid:phase4-tools`; it includes previous API/reliability work and all existing tool implementations. Compose uses the same service, HTTPS port, credentials, retained live policy and named state volume. The standard build/update remains:

```powershell
docker compose build
docker compose up -d --no-build
```

Raw data, credentials and saved private evidence remain excluded from image layers. Compose adds read-only bindings under `/app/evidence` for five prediction-v1 aggregate/freeze JSON files, the existing rolling and unseen-dataset confirmation summaries, and the saved synthetic research directory. Prediction arrays, local pair rankings and held-out label files are not mounted. The research verifier reads its existing observation database in explicit SQLite read-only mode; no observations are added. The root filesystem, inputs and evidence remain read-only, workers remain network-denied, and CPU/memory/process limits remain unchanged.

At admission, each new job saves a private typed binding containing exact paths and hashes of available operator-mounted evidence. Its binding hash is retained in API metadata before dispatch. That binding is captured in the existing scientific input identity/checkpoint. Forecasting verifies the pinned files and event-source hash before consuming a selection or rolling evaluation. Research keeps its manifest/artifact verification. Changed/missing evidence cannot silently substitute another evaluation or a community analysis. Source files must remain mounted at the same paths for recovery; an operator must review a change before starting a new investigation.

The Windows-saved research bundle needs an explicit [API belief portability profile](../protocols/api_beliefs_portability_v1.md) for Linux replay. Hashes, observations, specification, posterior parameters and non-derived types remain exact; only derived finite probability/interval decimals have the registered 1e-12 absolute/relative tolerance. Source files and reported values are never rewritten. The profile is recorded in the pinned job identity and `research_verification_profile` result field. Original benchmark/CLI verification retains its exact default. The prior cross-platform mismatch and failed acceptance are retained in the integration report.

Structural/community/behavior analyses use the bounded selected graph/window. As in the original forecasting tool, prospective rankings use **all validated observed history** through the recorded fixed cutoff and the registered horizon. The first-window context is not relabeled as a full-history forecast sample; forecast output states its distinct scope. Forecast fitting/candidate construction can take longer and use more memory than descriptive tools, under the same overall 930-second wrapper deadline and Docker limits. This integration is not a latency optimization.

Existing queued jobs retain their original `community` routing on migration, rather than changing scientific behavior during recovery. New jobs receive `auto` routing. Ownership, idempotency, cancellation, atomic reservations, safe mock recovery and conservative uncertain-live holds remain in force. No paid verification is needed to deploy the code. Before replacing the service, check active work and take a private consistent ledger backup; never restore an older spending database over newer charges.

## Acceptance

Verification is recorded in [the integration report](production_phase4/all_tools/report.md). Tests use synthetic data and fixture provider responses with container networking disabled, including a semantic planner choice for a question without routing keywords. The all-tools end-to-end test must observe all 18 tools across actual authenticated API jobs and contained CLI workers, not merely inspect the registry. Missing/wrong-source forecast evidence, privacy projections, read-only research verification and legacy routing are also checked. Real service acceptance uses mock questions and retained read-only local artifacts; it makes no paid provider calls.
