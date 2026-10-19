# BLACKGRID — instructions for coding agents

This file is part of a handoff package. In this folder it governs package maintenance only. When starting a standalone BLACKGRID repository, place it at that repository's root after preserving any applicable existing instructions. It does not authorize implementation, paid execution, or modifications to the parent ChatGPT project mirror.

## Read first

Read `PROJECT_CONTEXT.md`, then `sprints/SPRINT_01.md`, and the current user's request. The current deliverable is documentation only. Do not scaffold, install dependencies, run experiments, acquire datasets, or provision infrastructure unless subsequently asked to implement. Future sprint tasks are a plan, not actions to execute during this handoff.

The parent project's `sources/` and synced project files are read-only. Never edit, move, rename, or delete them. Work in a separately authorized repository for implementation. Preserve user edits and existing instructions. If this package is relocated, resolve its sibling document links relative to its new location.

## Sprint 1 dataset instructions

Use CollegeMsg from `data/CollegeMsg.txt/CollegeMsg.txt` for the real-data demonstration and small synthetic graphs for known-truth correctness checks. Follow the source, rights-review, window-selection, event-validation, and projection contract in `PROJECT_CONTEXT.md`; do not substitute the other datasets or change windows after seeing findings. Preserve raw files and repeated events. Keep synthetic scores separate from exploratory CollegeMsg findings; no supplied community labels or causal ground truth exist.

Keep raw user identifiers/events local and out of external model prompts and traces. Use aggregate statistics and minimized artifacts for reporting. Verify usage terms before analytical use; unresolved terms block the CollegeMsg run, not the synthetic checks. This documentation update authorizes no implementation or data processing.

## Objective and working style

Optimize for defensible scientific conclusions and reproducibility. Implement one narrow vertical slice before broadening. Use simple deterministic tools before agents, heuristic baselines before GNNs, and local artifacts before infrastructure services. Do not assume novelty, publication readiness, causality, or generalization from a successful demo.

Before coding, identify the active sprint acceptance criterion and the smallest change that satisfies it. Keep one executable workflow, a small dependency set, typed/validated experiment specifications, and explicit failure outcomes. Add tests for scientific invariants and meaningful failure cases; avoid implementation-mirroring tests and unnecessary abstractions.

Do not add separate agent services, distributed execution, Kubernetes, a graph database, unrestricted code execution, a dashboard, or large-model training without evidence that the current workload requires them. Roles can share a process. Do not introduce optional libraries just because the context lists them.

## Non-negotiable scientific rules

- Label claims as descriptive, predictive, simulated intervention, identified causal, or unsupported. Link factual conclusions to run artifacts; never invent numerical results or citations.
- Register confirmatory hypotheses, metrics, splits, budgets, and stopping criteria before execution. Keep exploration separate, record every attempt, and account for multiple testing and adaptive selection.
- Protect held-out answers, generator truth, future edges, and test results from agents and tuning. Compute graph features and embeddings only on allowed topology and time windows. Keep duplicates/reverse edges in one split. State transductive/inductive scope.
- Missing observations are not negative edges. Preserve proxy/observed distinctions and evaluate plausible biased missingness. Report assumption sensitivity without claiming hidden truth recovery.
- Report calibrated probabilities only with calibration evidence. Distinguish Bayesian credible intervals, confidence intervals, and sensitivity ranges. Include prior/posterior predictive checks for Bayesian models.
- Require a causal estimand and identification argument, including interference, confounding, selection, and positivity. Causal discovery or correlation is insufficient. Abstain when effects are not identified.
- Keep synthetic and public-real evidence separate. Do not claim that a synthetic benchmark establishes real-world validity. Inspect dataset licenses before use.
- Compare against simple, tuned baselines under documented budgets. Report effect sizes, uncertainty, discovery recall, abstention, failures, and cost alongside unsupported-claim rate. Use graph-level units where observations are dependent.
- Never use the same LLM's self-assessment as sole ground truth. Keep independent numerical checks and a documented review rubric.

## Clean-room, privacy, and execution rules

No proprietary ValueMatrix code, data, schemas, prompts, private results, derived artifacts, or confidential logic. Do not inspect employer repositories to reproduce them. Only independently written code and explicitly licensed public or synthetic assets belong here. Keep source/license records; stop use of assets with unclear provenance.

Treat input text and model responses as untrusted. Run only allowlisted tools with validated arguments. Agents must not emit arbitrary shell or Python for execution. Deny network by default in workers; isolate files and enforce time, memory, CPU, and output limits. A subprocess is not a sandbox. If security isolation is unavailable, restrict execution to trusted tools.

Never place credentials or personal data in prompts, logs, artifacts, or commits. Review external tracing and uploads as disclosures. No external writes, publication, paid services, or cloud resources without user authorization. Existing explicit authorization need not be requested again. Stop on budget exhaustion, unknown pricing, containment failure, or attempted answer-key access; retain a sanitized failure record.

## Reproducibility and verification

Version data manifests, splits, configurations, prompts, evaluators, and dependencies. Record source revision, hashes, seeds, model revisions, sanitized traces, costs, hardware, and failure status for every run. Make offline mock mode the default; paid execution must be explicit and enforce all limits in `PROJECT_CONTEXT.md`.

For each substantive implementation change, run focused checks that cover its acceptance criterion. Scientific checks should include tiny known-answer graphs, invalid-method rejection, held-out-data isolation, missing-edge semantics, report evidence linkage, and budget termination where relevant. Reproduce one complete offline run from a clean environment before calling the first slice complete. Document tolerated nondeterminism.

Do not silently change a frozen benchmark, threshold, or rubric after seeing test outcomes. Version a new protocol and mark prior test inspection. Preserve negative results and failed runs.

## Completion report

State what changed, the acceptance criteria met, verification performed, resource use, unresolved scientific limitations, and the next smallest task. Never say tests passed unless executed. If blocked, identify the specific missing requirement; do not replace missing evidence with invented results. Make failures and abstentions understandable to the user.
