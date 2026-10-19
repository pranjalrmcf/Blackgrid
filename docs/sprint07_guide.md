# Sprint 7: reliability, beliefs and next experiments

For the follow-up routing, scope, explanation and forecast-summary repairs, see
[`current_system_repairs_v2.md`](current_system_repairs_v2.md). Restart the console
to load the changes and start new investigations; historical runs retain their original versions.

The new path is a free, deterministic synthetic research demonstration. It does
not turn CollegeMsg scores into probabilities or estimate real-world influence.

From the repository root, create a fresh run:

```powershell
uv run --frozen blackgrid sprint7 --output runs/my-sprint7
```

Open `runs/my-sprint7/report.html`, or find the investigation in the existing
`blackgrid console`. The sections explain:

- **Reliability:** sigmoid calibration diagnostics and fixed reliability bins;
  independent-graph bootstrap uncertainty; refusal of a confidence interval for
  the existing two-window real-data example.
- **Beliefs:** exact Beta–Bernoulli updates for success across independent
  simulated tasks, including model-dependent credible intervals.
- **Next experiment:** candidate EVSI, artificial utility costs, next-action/stop
  rationale and prior/cost sensitivity. Real forecast VOI remains unavailable.
- **Causal assumptions:** a known-truth synthetic ATE example and informative
  CollegeMsg non-identification. A DAG cannot validate its substantive assumptions.

The initial uniform-prior state makes one experiment worthwhile. After observing
one outcome, no further single experiment changes the terminal choice enough to
justify its cost. This illustrates myopic stopping; it is not a globally optimal
research policy or an empirical graph-algorithm selection system.

Verify/replay an existing run without taking new observations:

```powershell
uv run --frozen blackgrid sprint7 --output runs/my-sprint7 --replay
```

Replay checks artifact hashes and reconstructs beliefs from SQLite observations.
Duplicate IDs do not update twice; conflicting receipts fail. Do not reuse an
output directory for a new run. Historical attempts are preserved.

For cancellation, create a file named `CANCEL` inside the in-progress run folder.
The next trusted operation boundary records cancellation. These bounded operations
finish quickly. Limits are cooperative, not an OS security sandbox or a preemptive
memory cap. Only registered trusted numerical code executes.

The mock research facade exposes `reliability_audit`, `belief_update`,
`experiment_decision` and `causal_identification_check`. It accepts tool names
only, with no caller-supplied outcomes, file paths, priors, utilities or code.
It is now integrated into the existing natural-language LangGraph planner. Try
the **Review research evidence** example in the console, or run:

```powershell
uv run --frozen blackgrid run configs/collegemsg_sprint01.json --family auto --planning-mode single --question "Review Sprint 7 uncertainty, posterior beliefs, next experiment and causal identification."
```

Other supported examples: "What are the posterior beliefs?", "Show calibration
uncertainty", "What experiment should I test next?", and "Check causal
identification assumptions". The planner selects the relevant registered tools;
the controller adds missing required tools and the critic checks exact claims.

The main workflow inspects the completed **`runs/sprint7-final`** reference.
If it is missing, prepare it once with `blackgrid sprint7 --output runs/sprint7-final`.
The evidence manifest hash is pinned before planning and included in the durable
run identity. Changed or missing evidence produces an incomplete answer. It does
not silently run a new benchmark, update beliefs from model text, or change the
experiment utility. The selected CollegeMsg graph is context, not evidence for
these synthetic conclusions.

Normal workflow cancellation, checkpoint recovery, budget accounting and replay
apply. A research inspection does not take new numerical observations. New
numerical experiments remain available through the separately scoped `sprint7`
command. Live explanation is opt-in under the existing allowance rules; integration
verification used mock/replay only.

## Reproduction

Use a new environment synchronized offline from `uv.lock` (see the verification
record for the exact dependency set), then:

```powershell
python scripts/verify_sprint7.py --python runs/sprint7-clean-env/Scripts/python.exe --name my-clean-source
```

The verifier copies source/tests/configs/protocols only into a fresh folder,
executes the demonstration and replay, runs focused invariants, and compares
scientific JSON against the versioned aggregate reference hashes in
`results/sprint07-v1/scientific_hashes.json`. It copies no raw data or secrets.
The name must be new. Timings, paths and environment receipts may differ;
registered numerical artifacts are expected to match exactly on this runtime.

Results, seeds, resource limits and assumptions are fixed in
[`sprint07_decisions_v1.md`](../protocols/sprint07_decisions_v1.md).
