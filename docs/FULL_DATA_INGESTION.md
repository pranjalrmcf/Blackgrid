# Using the full CollegeMsg data

The `ingest` command reads the entire recorded file, verifies its checksum and format,
and describes the network. It saves aggregate counts and hashes, not raw events,
person identifiers, individual connections or a copy of the source dataset.

From the repository directory, after applying these changes:

```powershell
uv run --frozen blackgrid ingest configs/collegemsg_sprint01.json --data-root . --output runs/full-collegemsg-v1
```

Choose a new output directory for each execution. Existing reports are never overwritten.
No API key, LLM, network access, new dependency or paid service is needed.

## What was measured on 18 October 2026

| Item | Full file |
|---|---:|
| Directed message events | 59,835 |
| People with recorded activity | 1,899 |
| Distinct directed pairs | 20,296 |
| Distinct undirected connections | 13,838 |
| Exact duplicate rows retained and flagged | 37 |
| Malformed rows | 0 |
| Self-loop events | 0 |
| Connected components | 4 |
| People in the largest component | 1,893 |
| Weekly bins anchored to the first event | 28 |

Events span 15 April to 26 October 2004 UTC. An event is a message record;
a connection combines all messages between two people, in either direction.
The simpler graph loses message direction, frequency and timing. Weekly counts
retain an aggregate view of activity through time, including empty bins if present.

## Ingestion versus research

Ingestion means checking and preparing the data. It does not prove that groups exist,
measure a causal effect, or make the agent capable of analysing the whole graph yet.
The historical experiment still uses the frozen first seven days and its existing
size limits. The full graph exceeds those limits. Increasing the experimental scope
requires a new versioned experiment, runtime budget and scientific checks.

That versioned experiment now exists: **exp-v2-full** (`protocols/full_dataset_experiment.md`,
`configs/collegemsg_full.json`, decision D-054). Run it with
`uv run --frozen blackgrid run configs/collegemsg_full.json`. It is exploratory and separate;
the first-week experiment and its result are unchanged.

Unobserved connections remain unknown; missing messages do not prove people have no
relationship. The existing local non-commercial use decision is retained with citations;
it does not establish permission to redistribute the raw dataset.

## Current delivery status

The prepared changes were applied to `C:\Blackgrid` on 18 October 2026 after
all eight package files passed baseline and content hash checks. The replaced CLI
is preserved in `ingestion-backup-20261018T094636329704Z/`.
Full ingestion was rerun locally; its aggregate report is saved at
`runs/full-collegemsg-applied-v1/ingestion.json`. See
`../results/full-collegemsg-v1/VERIFICATION.md` for verification evidence.

Sprint 3's offline validation benchmark, independent scoring, paired mock evaluation
and actual CPU Leiden comparison are now implemented and executed. The earlier
staging environment's package-access blocker was resolved in this repository.
See [the Sprint 3 report](sprint03_report.md) for separate synthetic evidence,
remaining unsupported claims, verification and follow-ups. No full-network CollegeMsg
community test or change to the original experimental window is included.
