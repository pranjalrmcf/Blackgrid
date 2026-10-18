# Using BLACKGRID's structural investigations

The console uses a dark futuristic theme. Its **Investigation engine** selector offers **Real AI · DeepSeek Flash** when paid mode is enabled at startup, alongside the free scripted demo. Switching engines updates the explanation; starting an investigation uses the selected engine. The retained allowance is displayed beneath the start controls. Real AI remains visible but unavailable when the console starts without `--allow-paid`.

Sprint 5 adds four tools to the existing three: centrality, descriptive partitions, cross-community connections and ranking sensitivity. They run through the existing durable workflow and local console. No API spend is needed for mock mode.

## Ask a structural question

From the repository root:

```powershell
uv run --frozen blackgrid run configs/collegemsg_sprint01.json --family auto --question "Which nodes have many contacts and high betweenness?"
```

For connections between detected groups:

```powershell
uv run --frozen blackgrid run configs/collegemsg_sprint01.json --family auto --question "Which nodes connect different groups, and are the rankings stable?"
```

The existing configuration selects the first-week graph. Use `configs/collegemsg_full.json` to explicitly select the pooled full dataset. Structural investigations are descriptive and exploratory in either scope. They do not run the community significance experiment merely because its seed/resource container is present in the configuration. Actual structural settings are recorded in `structural_contract.json`.

`--family auto` uses a deliberately narrow rule-based interpretation of community, centrality and bridge wording. It is not a general natural-language understanding benchmark. Unsupported or ambiguous questions, including actual influence and future prediction, receive a clarification/refusal. Edit the question to specify the structural measure you want.

By default, structural investigations permit one LLM follow-up decision after the initial results. It may request the fixed ranking-sensitivity tool once. Use `--planning-mode single` to disable that round. If stability is explicitly requested, it is required in the original plan in either mode.

Mock roles are scripted. Their choices exercise the workflow; they are not real-model reasoning. Live/replay modes use the same provider and durable controls. Real-model structural checks have now run; see [the live report](sprint05_live_report.md) for both initial failures and the fresh check after repairs.

## Inspect the result

```powershell
uv run --frozen blackgrid console
```

Open the local URL printed by the command. The home page accepts a question and offers three examples. The default console starts free demo runs only.

To use the existing authorized allowance with real AI, stop the old console with Ctrl+C and restart:

```powershell
uv run --frozen blackgrid console --allow-paid
```

Select **Real AI · DeepSeek Flash**, then **Start investigation**. The page shows the remaining allowance. It is USD 0.50 total for this task's trial and console together, not per run; restarting preserves prior spending. Each investigation is capped at USD 0.15 or the smaller remaining allowance, and all existing project/token limits still apply. The next unaffordable reservation is refused before dispatch. Unknown pricing blocks paid calls.

Paid console runs default to one plan to reduce unnecessary calls. Questions explicitly requesting stability still require its calculation. An optional follow-up decision can be enabled under **Experiment settings and system checks**. The free demo and recorded replay do not charge the provider.

- **Answer:** the question, a plain-language interpretation, sensitivity results and data scope. Detailed run diagnostics are collapsed below.
- **People & positions:** local node tables for degree/betweenness or cross-community connections, shared tie ranks, approximation status, partition metadata, removal sensitivity and the follow-up decision. Click a heading to sort the displayed subset. At most 500 rows are sent to the browser; all rows remain in the local JSON artifact.
- **Evidence:** expand a claim to see its cited value. Structural prose outside the registered claim forms is unassessed/rejected rather than automatically verified.
- **Activity:** proposed plan, validator reasons, model/rule calls, actual tool calls, cache use and errors. **Cost** shows accounting details; **Statistics** retains the community experiment view.
- **Run comparison:** compare two saved runs with the same graph projection and scope and a common ranking tool. This compares recorded summaries; it does not establish a causal effect.

Every completed investigation also writes `report.md`, `report.html`, the structured outputs and hash-linked manifest. Static snapshots show the saved results; interactive run comparison is available in the live local console.

Node references and individual rankings stay local and are excluded from external model evidence. A saved page containing node references is a local data artifact, not automatically a publication-safe export. Network dots retain the existing degree coloring and are not community labels.

## What the measures mean

Degree counts distinct contacts in the projected graph. Betweenness measures how often a node lies on shortest paths, using global graph normalization with unreachable pairs contributing zero. Through 200 nodes it is exact; larger graphs use 128 seeded sources. A sampled normalized estimate is not a calibrated probability and is not clipped to one.

The bridge ranking counts links crossing the saved partition; the accompanying fraction divides that count by the node's degree. Isolated nodes have fraction zero. A bridge ranking depends on the chosen partition and is distinct from bridge edges and articulation points.

Ranking sensitivity removes a floor-rounded 10% of edges three times, retaining all nodes and marking removed pairs unknown. It reports tie-inclusive top-five Jaccard overlap and average-rank Spearman correlation. A constant ranking has undefined correlation. Tiny graphs may lose no edges; inspect the recorded removal count before interpreting stability. These are sensitivity summaries, not uncertainty intervals.

Structural `supported` means that the required descriptive calculations produced usable evidence. It does not mean statistically significant community structure, actual influence or causal importance. The legacy community investigation retains its separate statistical verdict semantics.

## Reproduce the offline engineering evaluation

```powershell
uv run --frozen blackgrid sprint5 --output runs/NEW_SPRINT5_DIRECTORY
uv run --frozen python scripts/verify_sprint5.py runs/NEW_SPRINT5_DIRECTORY
```

The output directory must be new. This executes the frozen scripted comparison on 16 independent synthetic graphs, three arms each. Previously inspected instances are development evidence if rerun. See [the protocol](../protocols/sprint05_evaluation.md) and [the report](sprint05_report.md).
