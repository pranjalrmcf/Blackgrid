# BLACKGRID — Sprint 1 report

Date: 2026-10-18. Scope: Days 1–14 of `SPRINT_01.md`, plus a user-requested static UI and a gated OpenRouter adapter (D-029). Every number below is linked to a decision-log entry and a run folder under `runs/` (local, not committed).

## What was built

| Area | Delivered |
|---|---|
| Data contract | Checksum-verified CollegeMsg loader; schema checks; duplicate/self-loop accounting; frozen size-only window; undirected projection (D-013–D-016) |
| Synthetic benchmark | 8 dev cases, 4 families, 4 task types, evaluator-only answer keys, split policy, sealed-test reservation (D-019–D-021) |
| Experiment | Preregistered exp-v1 (D-023) and disclosed amendment exp-v1.1 (D-030). Louvain modularity vs an in-house degree-preserving null; suitability abstention; deterministic verdict; R = 499 by runtime rule (D-024) |
| Sensitivity | 10% uniform edge removal × 20; removed pairs become *unknown*, not non-links |
| Execution | Allowlisted tools with strict schemas, size caps, prerequisite and preregistration checks, network guard, deadlines, cache, answer-key stop (D-031) |
| Agent | Bounded planner/analyst/reviser loop; mock, OpenRouter (gated), and replay providers; worst-case budget reservation (D-031, D-035) |
| Critic and report | Rubric critic-v1 (R1–R7); plan validator; evidence-linked report whose numbers are machine-checked (D-031) |
| Evaluation | Mock pilot, tool_only vs validated, evaluator eval-v1 (D-032) |
| UI | Static offline console per run, pilot page, run index (`blackgrid ui`) |
| Reproducibility | Clean-environment offline rerun identical except timings and IDs (D-034) |

## Results

**CollegeMsg, first-week window** (descriptive; mock agent, real statistics; D-028, D-033):

- **Primary test.** Observed modularity Q = 0.587 against a degree-preserving null mean of 0.593 (499 nulls); p = 0.718. **Verdict `not_supported`**: no evidence of community structure beyond what the degree sequence produces.
- **Largest component** (87 nodes): p = 0.252.
- **Flags:** disconnected (8 components); degree confound (hubs).
- **Sensitivity:** 20 of 20 edge-removal replicates gave the same raw verdict.
- **Interpretation:** this does not show that communities are absent. It applies only to the 196 events in the projected window.

**Mock pilot** (plumbing only; D-032):

| Metric | tool_only | validated |
|---|---|---|
| Useful coverage (verdict and required flags) | 2/8 | 8/8 |
| Unsupported reported claims | 7/15 | 0/12 |
| Failures | 0/8 | 0/8 |
| LLM calls (mock) | 16 | 19 |

The mock analyst's mistakes are scripted. The evaluator shares rules with the critic, and two verdict rules were added after seeing dev failures (D-030). These numbers therefore show that the plumbing works and that the critic catches *those* mistakes. **They say nothing about whether the critic helps a real model.**

## Definition of done (SPRINT_01.md)

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Clean offline CollegeMsg run from documented steps, after terms review | **Met** | D-003, D-034 |
| 2 | Known-answer and null fixtures validate numerical tools and invalid input | **Met** | `test_experiment.py` oracles, `test_tools.py`, D-025 |
| 3 | Every factual claim linked to evidence; insufficient evidence abstains; causal claims rejected | **Met** | report number check; `test_cli`, `test_agent` causal and abstain tests |
| 4 | Generator truth excluded from planner, critic, and report, with an access test | **Met** | `planner_view`, leak-term tests, answer-key stop tests |
| 5 | Artifacts record config, versions, seeds, hashes, tool calls, failures, timings, cost | **Met** | `manifest.json` per run; claims hash-linked |
| 6 | Budget, retries, timeout, oversized graph, malformed call, unauthorized execution all terminate predictably | **Met, with stated gaps** | `test_agent`/`test_tools`. The timeout is a cooperative deadline, not a hard kill; memory is not capped on Windows; there is no OS sandbox (D-031) |
| 7 | Pilot reports unsupported claims and useful coverage with denominators; mocks labelled | **Met** | D-032, `pilot.json` |
| 8 | Sensitivity and window limitations in the report; synthetic results kept separate; no raw records sent externally | **Met** | `report.md`; prompts carry aggregates only (identifier test) |
| 9 | Loader checks and deterministic window and pair-aggregation tests; manifest counts | **Met** | `test_collegemsg*.py`, `data/manifests/collegemsg.json` |

**Live LLM run:** optional and **not done**. The adapter is gated and tested only on its refusal and redaction paths (D-035).

## Resource use

- **Money:** USD 0. No paid call was made.
- **Compute** (CPU, wall time):
  - CollegeMsg investigation: about 94 s uncached; seconds when cached.
  - Mock pilot: about 4 min uncached, about 5 s cached.
  - Full test suite: about 25 s.
- **Hardware:** Core Ultra 9 185H, 31.7 GB RAM, Windows 11. GPU unused.
- **Tests:** 138 tests in the repository (137 pass and 1 is skipped in the clean copy without data; all pass with data present).

## Unresolved limitations

- **The real-model behaviour is unknown.** Every agent result so far is mock.
- **The pilot is small and partly circular:** 8 engineering fixtures, an evaluator overlapping the critic, and dev-tuned rules A and B. It is not efficacy evidence.
- **The CollegeMsg window is tiny and sparse:** 104 nodes and 137 edges. The size-only rule picked the platform's first week, which may be unrepresentative. Changing it is not allowed after the fact (D-004).
- **Missingness is tested under one assumed mechanism only (uniform).** Degree-dependent and time-dependent mechanisms are untested.
- **Enforcement is in-process, not an OS sandbox.** It suffices for trusted in-repo tools only (D-031).
- **The UI is presentation only.** It adds no analysis.

## Go / no-go

**Go, conditionally**, to the next research step, because deterministic results, evidence linkage, containment checks, and offline reproduction all work. Before any claim about the critic's value:

1. Freeze a live-model pilot protocol and rubric: model ID, prompts (prompts-v1), critic-v1, eval-v1, budgets.
2. Run a small, authorized live pilot within the USD caps to estimate variance and cost.
3. Generate fresh **validation** cases (`val-NNN`) to re-check the adaptive rules A and B.
4. Only then size and open the sealed test set.

**Next smallest task:** confirm a working OpenRouter model ID and run one live validated investigation on CollegeMsg (estimated well under USD 0.50). Then replay it offline to verify the trace.
