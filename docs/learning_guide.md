# BLACKGRID — learning guide

What to learn alongside each sprint day, so you can read, defend, and extend what is being built. Each block lists:

- **Learn:** the concept.
- **In this repo:** where it lives.
- **Check yourself:** questions you should be able to answer before moving on.

Budget roughly 30–60 minutes of study per sprint day.

Readings are standard references. Get them from the publisher or the authors' pages, and verify the details before citing any of them in a report.

---

## 0. The one-paragraph picture (read first)

BLACKGRID asks a narrow question about one small graph, then tries to answer it honestly. The question: is the community structure in a bounded CollegeMsg window stronger than chance, and does that survive missing edges?

"Honestly" means five things:

- the method is chosen before the result is seen;
- the result is compared against a null model;
- every claim points to a stored artifact;
- the system abstains when evidence is weak;
- an agent never sees the answer key.

The long-term research question is whether adding a statistical validator and critic to a tool-using agent reduces unsupported conclusions. Sprint 1 only builds the plumbing to measure that.

Read in this order: [PROJECT_CONTEXT.md](../PROJECT_CONTEXT.md) → [sprints/SPRINT_01.md](../sprints/SPRINT_01.md) → [protocols/sprint01_protocol.md](../protocols/sprint01_protocol.md) → [decision_log.md](decision_log.md).

---

## Days 1–2 — Research hygiene and the tooling (already built)

**Learn**

- **Exploratory vs confirmatory research, and preregistration.** Why the window rule and method are frozen before any result exists. Look up "garden of forking paths" (Gelman & Loken) and "researcher degrees of freedom."
- **Evidence levels.** The difference between *descriptive*, *predictive*, and *causal* claims. Why "node X is central" is not "node X is influential."
- **Data provenance and rights.** Checksums (SHA-256): what a hash guarantees (the bytes are identical) and what it doesn't (that the data is correct). Why "publicly downloadable" ≠ "licensed."
- **Python tooling:**
  - `uv`: lockfiles, and why `uv.lock` plus `--frozen` gives reproducible installs.
  - `pydantic` v2: models, validators, `extra="forbid"`, `frozen=True`.
  - `pytest`: fixtures, `tmp_path`, `parametrize`.

**In this repo:** [contracts.py](../src/blackgrid/contracts.py), [cli.py](../src/blackgrid/cli.py), [pyproject.toml](../pyproject.toml), [uv.lock](../uv.lock).

**Check yourself**

1. Why does `RunConfig` reject an unknown field like `answer_key_path` instead of ignoring it?
2. Why must a completed result's p-value equal exactly `(1 + exceedances)/(1 + replicates)`?
3. What does `exclude-newer` in `pyproject.toml` protect against?

---

## Day 3 — Temporal networks, projection, and the loader (today)

**Learn**

- **Graph basics:**
  - nodes and edges; directed vs undirected; simple graph vs multigraph;
  - degree, connected components, density;
  - NetworkX `Graph`, `add_edge`, `number_of_edges`, node and edge attributes.
- **Temporal (event) networks.** A messaging dataset is a list of timed events `(u, v, t)`, not a static graph. Turning it into a graph throws information away (order, frequency, direction).
  - Reading: Holme & Saramäki, "Temporal networks," *Physics Reports* (2012), introduction only.
- **Projection choices and their consequences.** Here, "≥ 1 message in either direction ⇒ one undirected edge." Ask what a single message represents versus 500 messages between the same pair.
- **Half-open intervals `[t0, t0 + d)`.** Why they avoid double-counting at boundaries.
- **The dataset itself.** Panzarasa, Opsahl & Carley (2009), *JASIST* 60(5). Skim how the data was collected and what the platform was.

**In this repo:** [collegemsg.py](../src/blackgrid/data/collegemsg.py), [synthetic.py](../src/blackgrid/data/synthetic.py), [data/manifests/collegemsg.json](../data/manifests/collegemsg.json).

**Check yourself**

1. The full file has 20,296 distinct *directed* pairs but 13,838 *undirected* pairs. Why are these different?
2. 37 rows are exact duplicates. Why does the loader flag them instead of deleting them?
3. The 7-day window has 104 nodes and 137 edges. Why might the *first* week be much quieter than later weeks? Why are we still not allowed to pick a "better" window?
4. Why did a graph ID like `tiny-sbm` count as an answer-key leak?

---

## Day 4 — Synthetic benchmarks and known truth

**Learn**

- **Random graph models:**
  - Erdős–Rényi G(n, m) and G(n, p);
  - the stochastic block model (SBM), where `p_in` vs `p_out` sets community strength;
  - degree-heterogeneous models (configuration model; power-law-ish degrees).
- **Ground truth vs algorithm objective.** Planted SBM labels are what the generator did. A modularity-maximizing partition is what an objective prefers. They can disagree, especially when signal is weak (the "detectability limit").
- **Development / validation / sealed test splits.** Why the test set is untouched until protocols are frozen.

**Reading**

- Barabási, *Network Science* (free online), chapters 3 (random networks) and 9 (communities).
- Fortunato & Hric, "Community detection in networks: a user guide," *Physics Reports* (2016). Sections on benchmarks and validation.

**Check yourself**

1. In an SBM with `p_in = p_out`, are there communities?
2. Why must repeated runs of a model on the *same* graph not be counted as independent samples?

---

## Day 5 — Community detection, modularity, and null models (the core science)

This is the most important day to study deeply.

**Learn**

- **Modularity Q.** Its formula, what the "expected edges" term assumes (a degree-preserving random graph), and its range.
- **Louvain and greedy modularity optimization.** They are heuristics; results depend on seed and node order.
- **Known pitfalls of modularity:**
  - **Resolution limit** (Fortunato & Barthélemy, *PNAS* 2007): small communities can be merged.
  - **High modularity in random graphs** (Guimerà, Sales-Pardo & Amaral, *Phys. Rev. E* 2004): sparse random graphs can show high Q with no real structure. **This is why a null model is mandatory here.**
  - **Degenerate optima** (Good, de Montjoye & Clauset, *Phys. Rev. E* 2010): many very different partitions score nearly the same.
- **Degree-preserving null models.** Double-edge swaps (configuration-model sampling): what they preserve (degrees) and destroy (everything else). Reading: Fosdick et al., "Configuring random graph models with fixed degree sequences," *SIAM Review* (2018).
- **Monte Carlo p-values.** Why `(1 + exceedances)/(1 + replicates)` and never zero (Phipson & Smyth, "Permutation p-values should never be zero," 2010). Know these too:
  - p-value resolution;
  - why a small p-value is not an effect size;
  - why the *same* optimizer must run on observed and null graphs.

**Check yourself**

1. Our window is small and sparse (mean degree ≈ 2.6). Using Guimerà et al., predict what modularity a random graph of that size might show. What does that imply for interpreting our observed Q?
2. With 99 null replicates, what is the smallest p-value we can report?
3. Why would optimizing the observed graph harder than the null graphs bias the test?

---

## Day 6 — Missing data and sensitivity analysis

**Learn**

- **Missing ≠ absent.** An unobserved pair is *unknown*, not a confirmed non-link.
- **Missingness mechanisms.** Missing completely at random, missing at random, and missing not at random (from Rubin's framework). Degree-dependent or time-dependent missingness.
- **Sensitivity analysis vs uncertainty quantification.** Removing 10% of edges and re-running shows how *fragile* a conclusion is. It does not recover hidden truth.

**Reading:** Kossinets, "Effects of missing data in social networks," *Social Networks* (2006).

**Check yourself:** Why does the contract keep `UNKNOWN` and `KNOWN_NON_LINK` as separate edge statuses?

---

## Days 7–8 — Validated tool execution and a bounded agent

**Learn**

- **Tool-using LLM agents.** Planner → structured tool call → executor → observation, plus why outputs must be validated against a schema.
- **Safety basics:**
  - allowlisted tools only;
  - never execute model-generated code;
  - resource limits (time, memory, output);
  - why a subprocess is *not* a sandbox.
- **Prompt injection.** Data that contains instructions. Reading: Greshake et al., "Not what you've signed up for" (2023), plus the OWASP Top 10 for LLM Applications.
- **Budgets and stop rules.** Counting calls, tokens, retries, and cost *before* making a call.
- **Mock / replay mode.** Why deterministic fake responses let you test plumbing without paying, and why mocks prove nothing about LLM quality.

**Check yourself:** If an agent requests `method="arbitrary_python"`, where exactly in the code is it stopped?

---

## Days 9–10 — Critic, claims, and evidence-grounded reports

**Learn**

- **Claim–evidence linkage.** Every factual sentence maps to an artifact field with a hash.
- **Abstention as a valid outcome**, and the coverage–risk trade-off: abstaining always is "safe" but useless. That is why discovery recall is also measured.
- **Why an LLM grading itself is not ground truth.** Independent numerical checks and rubrics.
- **Causal claims require identification:** estimand, confounding, interference, positivity. Reading: Hernán & Robins, *Causal Inference: What If* (free online), chapters 1–3, just to recognize what is *not* allowed in Sprint 1.

**Check yourself:** Why would "high-degree students cause the network to cluster" be rejected even with a tiny p-value?

---

## Days 11–14 — Pilot evaluation, adversarial checks, reproducibility

**Learn**

- **Ablation studies and paired comparisons.** Same instances and budget, one component changed.
- **Metrics:** unsupported-claim rate (with numerator and denominator), discovery recall, empirical false discovery proportion vs formal FDR control.
- **Multiple testing.** Bonferroni and Benjamini–Hochberg at a conceptual level, and optional stopping.
- **Reproducibility:**
  - seeds vs bitwise determinism;
  - clean-environment reruns;
  - what a run manifest must record.

**Check yourself:** Why does a pilot on 8 mock fixtures tell you nothing about whether the critic helps a real LLM?

---

## Later phases (not Sprint 1, for orientation only)

| Phase | Topic | Starting point |
|---|---|---|
| 3 | Link prediction, leakage, GNNs | Hamilton, *Graph Representation Learning* (free online); temporal splits and negative sampling |
| 4 | Bayesian uncertainty | McElreath, *Statistical Rethinking*; Gelman et al., *Bayesian Data Analysis*. Posterior predictive checks and calibration. |
| 5 | Causal inference on networks | Hernán & Robins; interference and spillover literature |
| 6 | LLMOps | Tracing, evaluation regression suites, caching, routing |

---

## Suggested rhythm

1. Before each day, read that day's row in `sprints/SPRINT_01.md` and this guide's section.
2. After the day's work, open the new code and answer the "check yourself" questions *without* looking. Then verify against the code or tests.
3. Note any answer you got wrong in your own notes. Those are the concepts to revisit before Day 14's review.
