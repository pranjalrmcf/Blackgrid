# Sprint 3, in plain English

Sprint 3 gives the existing workflow a fresh set of synthetic graphs and checks its
saved answers independently. It also compares two ways of finding communities:
Louvain and Leiden. It does not change the historical CollegeMsg experiment.

## What runs

There are 24 fresh graphs. Eighteen cover clear and weak planted groups, random
connections, uneven degrees, disconnected pieces and missing observations. Six
carry requests that should be refused: arbitrary code or unidentified causal effects.
Each graph is examined in both `tool_only` and `validated` conditions.

The model is a fixed mock. Its first draft makes deliberate mistakes, and its revised
draft follows fixed templates. This checks execution and whether the critic catches
those mistakes. It cannot establish how a real model behaves.

The independent evaluator reads saved, checksum-verified evidence. It checks the
numbers, their meanings and citations, recomputes the statistical decision, and checks
that the required work and qualifications are present. Unrecognized wording is marked
unassessed. A graph's generator settings are not treated as its significance-test answer.

Louvain and Leiden examine the same 18 structural graphs with three seeds each.
For each seed they receive the same 99 randomized graphs. Both get five restarts;
Leiden gets two iterations per restart and Louvain runs to its own stopping rule.
Their scores use the same modularity formula. Equal restarts do not mean equal work.
Disconnected graphs also need a largest-component check. Missing observations remain
unknown; they are never silently treated as confirmed non-links.

## Reproduce locally

After installing the recorded environment once:

```powershell
uv sync --frozen --extra methods
uv run --frozen --offline --extra methods blackgrid sprint3 --output runs/sprint3-reproduction
uv run --frozen --offline --extra methods blackgrid sprint3-verify runs/sprint3-reproduction
uv run --frozen --offline --extra methods python scripts/verify_sprint3.py runs/sprint3-reproduction
```

Choose a fresh output directory on every run. Output must be under `runs/` because
the complete folder includes private evaluator mappings and local workflow state.
No API key or paid provider is used. Installation may require network access;
the scientific workflow denies network connections in-process.

The workflow records its protocol, source and dependency hashes before generating
graphs. It then records each attempt as it starts and finishes. Failed or incomplete
work stays visible. It uses one CPU task at a time, existing graph-size caps,
cooperative per-scope deadlines and a 45-minute total cooperative budget. It does
not provide an OS security sandbox or enforce a memory cap.

The completed Sprint 3 run is `runs/sprint3-v1.1`. An independent audit and a full
source-snapshot reproduction matched all 48 scores and 54 method artifacts.
See [the results report](sprint03_report.md) and
[aggregate receipts](../results/sprint03-v1.1/summary.json). To archive and compare
your own reproduction, the small `scripts/archive_sprint3_source.py` and
`scripts/compare_sprint3.py` helpers preserve frozen inputs and exclude only recorded
volatile fields. They copy no raw datasets, secrets or earlier run history.

## Read the artifacts

- `freeze.json`: exactly which code, protocol, settings and dependencies were used.
- `registry.json`: public questions, graph sizes and graph hashes, without answer keys.
- `attempts.jsonl`: every attempted condition or method comparison, including failures.
- `evaluation.json`: independent scores, denominators, paired comparisons and uncertainty.
- `method_summary.json` and `methods/`: method results, shared-null hashes, partitions,
  connectivity, runtime and seed stability.
- `blinded_claims.csv`: claims and cited evidence, with empty human-review fields.
- `evaluator_private/`: answer expectations and the separate condition mapping.
- `suite.json`: completion status, errors, timing and artifact checksums.

Human review remains pending until someone fills in the blinded review sheet. Its
condition labels are hidden, but the wording can still suggest which condition wrote it.
Do not give evaluator-private files to agent roles or publish the full run folder.

## What the results mean

An unsupported-claim rate needs its numerator and denominator. A system can reduce
that rate simply by saying nothing, so also inspect useful complete answers, failures,
abstentions, unknown wording and evidence-supported discovery coverage. Reported
bootstrap intervals resample whole graph cases, keeping each pair of conditions
together. They describe this exploratory scripted case mix; they do not show real-model
efficacy or generalization to a population of networks.

High modularity alone is insufficient evidence for meaningful communities. Even an
unusual structural pattern does not establish friendship, influence or a causal effect.
Keep Louvain the historical default unless a later decision justifies changing it.

Full CollegeMsg ingestion is a separate descriptive artifact: it validates all records
and exports aggregates. It does not authorize a full-network hypothesis test or raise
the old experimental size limits. See [the ingestion guide](FULL_DATA_INGESTION.md).
