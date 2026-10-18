# BLACKGRID — Full-dataset CollegeMsg experiment (exp-v2-full)

Status: **exploratory**. Written 2026-10-18, before the first full-dataset community test was run. Requested by the user ("use the whole dataset of college messages"). It is versioned separately from, and never replaces, the preregistered first-week experiment (`sprint01_experiment.md`, exp-v1.1), whose window, limits, config, and historical results are unchanged.

## 1. What was already known when this was written (disclosure)

- **The first-week result** (D-028, D-033): verdict `not_supported`, Q = 0.587 vs null mean 0.593, p = 0.718.
- **Full-file descriptive counts** from Codex's ingestion (D-050): 59,835 events, 1,899 people, 13,838 undirected connections, 4 components, largest component 1,893 people.
- **One observed full-graph Louvain modularity value** (Q ≈ 0.26), printed by a runtime-measurement script while sizing this protocol. No null comparison, p-value, or sensitivity result had been computed.

Because of these, nothing here is confirmatory. The result must not be pooled with, or presented as a correction of, the first-week result.

## 2. Scope and graph

Every valid event in `data/CollegeMsg.txt/CollegeMsg.txt`, using the same loader, checksum, validation, and projection as exp-v1:

- simple, undirected, unweighted;
- repeated and reciprocal messages are merged;
- self-loops are excluded and counted;
- exact duplicate rows are flagged and kept.

The whole roughly 193-day period becomes one static graph. That describes the aggregate network, not any moment in it.

The config is `configs/collegemsg_full.json` (`scope: "full_dataset"`, graph ID `collegemsg-full`). The run records the graph's time bounds and projection hash.

## 3. Method (unchanged from exp-v1.1 except where stated)

Same as exp-v1.1:

- the statistic and optimizer (Louvain modularity, best of 5 restarts, resolution 1);
- the in-house degree-preserving double-edge-swap null (10 accepted swaps per edge, 100× attempt cap);
- the same optimizer applied to every null;
- the p-value (1+E)/(1+R) with ties counted;
- the effect contrast (delta Q, z);
- alpha 0.05;
- suitability rules S1–S4;
- the secondary largest-component analysis (the graph has 4 components);
- the verdict rule, plus exp-v1.1 rules A (unobserved pairs) and B (degree-confound disclosure).

Changed, for runtime only (see §4):

| Setting | exp-v1.1 (first week) | exp-v2-full |
|---|---|---|
| Null replicates R | 499 | **99** (p resolution 0.01) |
| Sensitivity replicates | 20 | **5** |
| Nulls per sensitivity replicate | 99 | **19** (p resolution 0.05) |
| Per-tool time cap | 60 s | **1,200 s** |
| Node / edge caps | 1,000 / 10,000 | **5,000 / 50,000** |
| Investigation wall-clock limit | 900 s | **3,600 s** |
| Master seed | 20261017 | **20261018** |

## 4. Runtime rule

These were measured on this machine before any full-graph inference:

| Operation | Time |
|---|---|
| One Louvain fit | 0.15–0.22 s |
| One null graph | 0.69 s |
| One complete null replicate (swaps + 5 restarts) | about 1.6 s per scope |

The budget for the community test is about 6 minutes (whole graph + largest component). R = 99 is the largest of {99, 199, 499} within it; R = 199 would take about 10.5 minutes.

The sensitivity analysis is about 5 replicates × 2 scopes × 20 nulls × 1.6 s, about 5.3 minutes. The total is about 12 minutes.

**Consequence:** with 19 nulls, a replicate can only be "supported" if no null reaches the observed Q (p = 0.05). The sensitivity is therefore coarser than exp-v1.1's and is reported as such.

## 5. Reporting

The report:

- is titled `exp-v2-full, exploratory`;
- states the pooled-time and reduced-sensitivity limitations;
- keeps every exp-v1.1 report safeguard (evidence links, number checks, critic, flags).

Evidence level: descriptive, for the observed projected network only. No causal, predictive, or real-social-group claims.

## 6. What would change this protocol

Changing the time window, resolution, method, R, or thresholds after seeing this run's result requires a new version (exp-v2.1+) with a decision-log entry, and every prior run is kept.
