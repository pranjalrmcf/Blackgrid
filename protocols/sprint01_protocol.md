# BLACKGRID — Sprint 1 protocol (v0.1, Day 1)

Status: **exploratory pilot protocol**, drafted 2026-10-17 (Sprint 1, Day 1). Governs Sprint 1 only. Derived from `PROJECT_CONTEXT.md` and `SPRINT_01.md`; where this file is silent, those documents apply. Changes after any experimental outcome is inspected require a new protocol version and a decision-log entry (`docs/decision_log.md`).

No code, experiment, or community analysis has run. The only data operations performed so far are the provenance checks in §3.

## 1. Task

Research anchor (exploratory, RQ1/RQ2 pilot): *Is the observed community structure in a bounded CollegeMsg window stronger than expected under an appropriate null, and how sensitive is that conclusion to missing edges?*

Sprint outcome: one local, offline, reproducible investigation. A constrained (mock-first) agent selects a valid community-structure experiment, deterministic tools execute it, a rule-based critic checks the evidence, and a report either supports a narrowly worded descriptive conclusion or abstains. Synthetic known-truth fixtures validate the tools separately.

Evidence level ceiling for CollegeMsg: **descriptive observation** about the projected observed window. No predictive, causal, or substantive social-group claims.

## 2. Out of scope (Sprint 1)

Graph ML/GNNs, full Bayesian inference, causal estimation, temporal prediction benchmarks, custom serving, multi-agent services, UI, deployment, cloud/GPU, paid API calls (unless separately authorized), and the other local datasets (Bitcoin OTC, Reddit, Wikipedia talk, Stack Overflow).

## 3. Data source and provenance

| Field | Value |
|---|---|
| Dataset | CollegeMsg (SNAP) — directed private-message events, UC Irvine online community |
| Repo-relative path | `data/CollegeMsg.txt/CollegeMsg.txt` (immutable; never renamed/overwritten) |
| SHA-256 | `e00ba2415373dee52c00616065bcceaa4750e78de60d1855c76470600f10740f` |
| Size | 1,150,439 bytes; file mtime 2016-11-28T02:16:17Z |
| Format | whitespace-separated `source_id target_id unix_timestamp`, one directed event per row |
| Source page | https://snap.stanford.edu/data/CollegeMsg.html (derived by SNAP from a dataset hosted by Tore Opsahl) |
| Citation (SNAP) | P. Panzarasa, T. Opsahl, K. M. Carley. "Patterns and dynamics of users' behavior and interaction: Network analysis of an online community." *JASIST* 60(5):911–932, 2009. |
| Citation (Opsahl page) | T. Opsahl, P. Panzarasa. "Clustering in weighted networks." *Social Networks* 31(2):155–163, 2009. |

Day 1 provenance check (aggregate only, streamed locally, no identifiers printed or sent anywhere):

| Check | Local file | SNAP published |
|---|---|---|
| Valid rows / temporal edges | 59,835 | 59,835 |
| Malformed rows | 0 | — |
| Distinct node IDs | 1,899 | 1,899 |
| Timestamp range (UTC) | 2004-04-15T14:56:01 → 2004-10-26T07:52:22 | — |
| Span | 193.71 days | 193 days |
| Timestamp decreases in file order | 0 (file is time-sorted) | — |

Conclusion: the local file is consistent with the published release at the level of these counts. Self-loops, repeated pairs, exact-duplicate rows, and static-edge count (published: 20,296) are checked by the tested loader on Day 3, not here.

## 4. Usage-rights review

Findings (2026-10-17, from the two source pages above):

- Neither the SNAP dataset page, the SNAP dataset index, nor the Opsahl datasets page states a license, terms of use, or redistribution grant.
- SNAP *encourages* citation; Opsahl's page asks users to cite the listed reference.
- Opsahl withholds nodal attributes because they could enable reverse-engineering of the anonymisation — a signal that re-identification risk is taken seriously.

Interpretation: public availability with a citation request is **not** an open license. Status is recorded as:

- **Redistribution of raw records: not permitted** (no grant found). Raw files stay local and out of any commit, artifact bundle, prompt, or trace.
- **Local, non-commercial analytical use with citation: accepted by the user for Sprint 1** (2026-10-17, decision D-003). The CollegeMsg run is unblocked for this sprint. This is a user decision, not a verified license, and must be revisited before any public release.
- Published reports may contain aggregate statistics only, with both citations.

## 5. Window and projection contract (frozen before any analysis)

1. `t0` = minimum valid timestamp in the file (observed: 1082040961).
2. Candidate windows, tried in order, half-open `[t0, t0 + d)`: d = 7 days, 3 days, 1 day, 6 hours.
3. Select the first window whose projection has ≤ 1,000 active nodes **and** ≤ 10,000 unique undirected non-self-loop pairs. Selection uses only these size counts.
4. If none fits, or the selected projection is unsuitable for inference (e.g., too few edges/nodes for the null comparison, as defined in the Day 5 experiment spec before execution), **abstain** and record the limitation. No other window may be chosen.
5. Active node = appears as source or target of ≥ 1 event in the window (self-loop-only nodes are counted and reported separately).
6. Preserve the selected directed event table with timestamps and repeated events; flag, don't delete, exact-duplicate rows.
7. Projection: simple undirected unweighted graph; edge {u,v} iff ≥ 1 message u→v or v→u in the window; self-loops excluded and counted. Direction and frequency are deliberately discarded.
8. Manifest records: window bounds, which candidate was chosen and why, raw/window/projected counts, exclusions, projection hash.

The window will be computed by the Day 3 loader under test; it is intentionally **not** computed on Day 1, so the first recorded selection comes from the reviewed implementation.

## 6. Experiment (outline; full spec frozen on Day 5 before execution)

- One preselected community method and statistic, applied identically (same algorithm, seeds policy, optimization effort) to observed and null graphs.
- Degree-preserving null (double-edge swaps) where feasible; documented handling of disconnected/small graphs and failed swaps.
- Fixed null-replicate count chosen on synthetic development cases within the 60 s tool cap; p-value reported as `(1 + exceedances)/(1 + replicates)` with stated resolution. No replicate changes after seeing significance.
- Report: observed statistic, null summary, effect contrast, limitations, and a prespecified edge-removal sensitivity analysis (labeled sensitivity, not uncertainty quantification).
- Synthetic fixtures (planted-community SBM, Erdős–Rényi null, degree-heterogeneous, disconnected/sparse) carry evaluator-only truth; their scores are reported separately from CollegeMsg.

## 7. Resource limits

- Machine (observed Day 1): Intel Core Ultra 9 185H (16 cores / 22 threads), 31.7 GB RAM (~11.7 GB free at check), 414 GB free disk, Windows 11, Python 3.11.9, `uv` and `git` available. NVIDIA RTX 4070 Laptop GPU present but unused in Sprint 1.
- Sprint limits: CPU only; one concurrent experiment; ≤ 2 GB worker memory; 60 s per tool call; graphs ≤ 1,000 nodes / 10,000 unique edges.
- Paid usage: **none authorized.** Mock/replay mode is the default and is sufficient for sprint completion. Ceilings in `SPRINT_01.md` apply only if later authorized.
- Effort: 16–20 focused hours; Day 1 used ~1 hour equivalent of agent work (documentation and checks).

## 8. Privacy and clean-room

Identifiers are pseudonymous; no re-identification, individual profiling, or per-user reporting. Raw events never enter external LLM prompts or telemetry. No ValueMatrix code, data, schemas, or logic. Web lookups made today fetched only public dataset documentation; no data was sent.

## 9. Acceptance evidence for Day 1

- [x] Task and sprint scope confirmed (§1–2)
- [x] Source, citations, checksum, and file consistency recorded (§3)
- [x] Usage terms reviewed; Sprint 1 analytical use accepted by the user (§4, D-003)
- [x] Window/projection contract frozen (§5)
- [x] Machine limits recorded (§7)
- [x] Decision log started (`docs/decision_log.md`)
