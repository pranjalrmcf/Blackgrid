# Sprint 5 development protocol: structural tools v1

Frozen before implementation and development execution, 18 October 2026. Exploratory engineering work; no real-model efficacy claim. Historical cases are regression evidence only.

Use simple undirected unweighted loop-free graphs, retaining isolated nodes. Structural calculations are descriptive. No causal influence, prediction or verified social group claims. Unknown pairs remain unknown. Raw node identifiers and rankings remain local.

Centrality: raw degree and normalized betweenness, using global n-node normalization (unreachable pairs contribute zero). Exact through 200 nodes; otherwise sample 128 sources uniformly without replacement using the experiment seed and scale by n/128. Report approximation. Ties share competition ranks, with deterministic node ordering for display. Top-k is five, including boundary ties. Compare with independent tiny-graph answers and the installed NetworkX reference.

Partition: Louvain resolution 1, five seeded restarts, highest modularity, deterministic tie-break; isolated nodes form singleton communities. Edgeless graphs have singleton partitions. A partition is not statistical support. Bridge metrics: cross-community degree and cross-community fraction (zero for isolated nodes). Rank by cross-community degree, not by inferred influence.

Ranking sensitivity: three independent uniform removals of 10% of original edges, floor-rounded, with fixed seeds derived from the experiment seed. Keep every original node. Recompute the relevant ranking and partitions for bridge analysis. Primary stability measure: Jaccard overlap of tie-inclusive top-five sets. Secondary: Spearman correlation of average ranks across all retained nodes; return null when either ranking is constant. No significance test or confidence interval. Removed edges are unknown, not negatives.

Question families: community (existing frozen procedure), centrality and bridge. Structural robustness requests require ranking sensitivity. Ambiguous influence and unsupported questions require clarification/refusal. Each structural plan runs at most six tool invocations, including at most one follow-up round of two tools. Follow-up cannot change the question, scope, metric or frozen settings. No duplicate tools. All tools use the existing trusted executor and resource caps.

First acceptance slice: centrality question executes through the existing durable workflow without community-null calculations; all ranks remain local; aggregate model evidence excludes node rows; structured descriptive claims bind to exact tool metadata. Preserve community-path regressions, budgets and replay integrity.

Later fresh evaluation requires its own frozen instance schedule and scoring before generation. Mock providers validate mechanics, not real LLM usefulness. Paid execution is not authorized by this protocol.
