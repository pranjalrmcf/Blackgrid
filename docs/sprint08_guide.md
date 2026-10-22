# Sprint 8: behavioral analysis

The main workflow and local console now support three descriptive analyses of directed messaging events. Use **CollegeMsg · first week** and the **Analyze behavior** example in the console. The current slice caps analysis at 1,000 nodes; the full CollegeMsg graph exceeds that limit and is explicitly refused.

| Ask | Result |
|---|---|
| “Find behavioral clusters.” | Fixed three-cluster KMeans on standardized activity features; cluster sizes, feature means, local membership and silhouette. |
| “Find similar activity profiles.” | Exact cosine search; select a local node to inspect its five nearest other profiles. |
| “Find anomalous messaging behavior.” | Robust feature-deviation candidates, strongest contributing feature, and a count-only baseline. |
| “Find behavioral clusters, similar activity profiles and anomalous messaging behavior.” | All three, sharing the same feature definitions and recorded observation window. |

For real AI under the existing absolute project spending ceiling:

```powershell
uv run --frozen blackgrid console --allow-paid --max-usd-total 3
```

Select **Real AI**, choose the first-week scope, and submit a question above. Open **Behavior & similarity** in the finished run. Restart an already-running console to load the new backend code. A retained allowance includes historical spending and unresolved reservations; it is never renewed by restarting.

The CLI also accepts `--family behavior` or `--family auto`. If `runs/console-project-allowance.json` already contains the authorized ceiling:

```powershell
uv run --frozen blackgrid run configs/collegemsg_live.json --family auto --question "Find behavioral clusters, similar activity profiles and anomalous messaging behavior." --allow-paid --live-allowance runs/console-project-allowance.json
```

The real planner selects registered tools. Trusted numerical code computes the results; the default writer uses exact evidence templates checked by the critic. Identifiers, memberships and neighbor rows stay in local artifacts and the console. The model sees aggregate summaries only. No extra library, service or training job was added.

## Feature and interpretation contract

Eight features describe sent/received event counts, distinct recipients/senders, fraction of seven time bins active, reciprocity, outgoing share and peak-bin concentration. Count features use `log1p`. Repeated events count; self-events are excluded and recorded. Only events within the exact recorded half-open window are used. Nodes with zero usable profiles are retained but excluded from clustering, similarity and anomaly fitting.

KMeans fits the observed population with fixed k=3. A silhouette is an internal separation diagnostic, not classification accuracy. Cosine search compares nonnegative profiles including volume; it does not show that two people know each other or will interact. Ties are broken by local numeric identifier. The anomaly rule uses maximum median/MAD deviation with fixed scale floors and cutoff 3.5. It is a heuristic ranking, not a statistical test or a calibrated detector. Each candidate has an ordinary behavioral explanation until independently investigated. No real-world anomaly labels exist here.

Too few or identical usable profiles produce explicit abstentions. Event/projection mismatches, missing event provenance, changed method arguments, incompatible tools and size-limit violations are rejected. A graph without directed events cannot be relabeled as behavioral data.

The [frozen protocol](../protocols/sprint08_behavior_v1.md) specifies features, scaling, thresholds and checks. [Implementation results](sprint08_report.md) distinguish numerical correctness, live integration and unresolved scientific validation.

The subsequent [24-question real-LLM evaluation](sprint08_system_evaluation_v1.md) achieved 22 strict passes. Its two comparison omissions were then repaired; the [repair report](sprint08_repairs_report.md) preserves that score and the intermediate 10/12 follow-up alongside a final 12/12 targeted confirmation.

Similarity search now includes **Compare behavioral features** beneath the selected node's neighbors. Combined clustering/anomaly requests include **Clusters compared with anomaly candidates**, plus cluster membership in the local anomaly ranking. Grouped outlier requests require both memberships and flags; oversized graphs receive an explicit refusal with the current limits. Restart a running console to load the backend changes.
