# Real-provider repair follow-up

19 October 2026. User requested actual LLM execution, no mock LLM, and an approximately USD 3 budget. All execution evidence below uses OpenRouter with `deepseek/deepseek-v4-flash-0731`; no mock or replay provider was executed. Direct unit tests do not simulate an LLM.

## Finding and repair

Production source hashes matched the previous v2 repair freeze: Claude had not changed production code. Its new mock evaluation exposed a pre-existing limitation of our keyword router. Real baseline calls confirmed that the model chose the appropriate community/centrality/bridge tools, but the controller rejected those valid plans because it classified the wording differently.

Auto mode now takes a bounded family from the real plan, or derives it from an unambiguous set of registered tool calls when the model omits the family field. Unknown families, mixed incompatible tools, invalid arguments and unsafe requests remain rejected. Explicit user-selected families remain authoritative. Required analyses are recomputed after selection, and the checkpointed request governs tools, critics, reports and resumed inputs. Potential synthetic evidence is pinned before planning using a trusted local manifest, never a model-provided path. Saved synthetic findings are still not evidence about real graph probabilities or causality.

First-time contacts between existing users remain new-pair predictions. An unsupported causal request is a refusal rather than a research review, even if the planner supplied a research label; its explanation is preserved and no numerical tool executes.

The initial repaired verification exposed another failure: socket timeouts did not bound the full HTTP exchange. Provider HTTP now executes in a small trusted child with a parent-enforced wall-clock deadline, bounded input/output and an endpoint allowlist. Credentials travel through private process pipes, never command arguments or files. Timeouts remain uncertain-billing outcomes and are not automatically resent. This isolates timeout handling; it is not an OS security sandbox. The provider transport checks the trusted-tool network guard before spawning, so tools cannot bypass their network restriction through this transport.

Provider requests prioritize latency and enforce upstream prompt/completion price limits corresponding to the existing 2x list-price reservation factor. These routing options are documented by [OpenRouter](https://openrouter.ai/docs/guides/routing/provider-selection). A preference is not a latency guarantee.

Both live console configuration files now match the successfully tested model/settings: 4,096 maximum completion tokens, 1,024 reasoning tokens, a 60-second HTTP deadline and latency routing. The retained-allowance constraint no longer silently increases an explicitly configured reasoning budget. Historical allowances and billing records were not renewed or reset. Scientific numerical specifications, data, splits, model parameters and cache keys were unchanged.

Versions: workflow `wf-v3.1`, prompts `prompts-v12`, critic `critic-v10 semantic-routing-v1 research-v2`. Historical runs cannot silently adopt the changed workflow. Restart an already-running console to load the code.

## Actual execution evidence

| Phase | Result | Interpretation |
|---|---|---|
| Real baseline, three known-billed cases | 0/3 useful; all three valid model plans rejected by old routing | Confirms the actual controller bug, rather than a mock-model artifact |
| Initial 24-case repaired verification | Four provider requests hit the 210-second external deadline; 20 cases never dispatched | Stopped and preserved; not a completed evaluation and not pooled with later successes |
| Six separately frozen prospective paraphrases | All completed in 53.87 seconds; 5/6 strict routing/answer passes | All five supported analyses correct. The causal request was safely refused, but mislabeled research; this failure remains in the original score |
| Four known-billed development confirmations after refusal-label repair | 4/4 passed in 29.98 seconds | Three original routing failures now execute correctly; the refusal now has the correct label and explanation. This is development evidence, not a rescored fresh benchmark |

The four unknown-billing requests were never resent. The later confirmation repeated only completed, known-billed cases under a new frozen development protocol. Structural data remain the fixed CollegeMsg first window (104 nodes, 137 edges); forecasts use the approved complete event history and saved rolling evaluation; research reads the registered saved synthetic demonstration. Normal numerical caches and saved forecast parameters were reused and disclosed. UI rendering was excluded from these concurrent runs; reports/manifests and numerical tools were exercised.

Independent audit checks every saved artifact hash and claim evidence pointer, checks numeric bindings, recomputes community Monte Carlo statistics, compares degree and direct NetworkX betweenness with the raw projection, recomputes cross-community counts/ranks, and checks forecast candidates, pair membership, score ordering, cutoff and historical metric equality. It also verifies the synthetic decision's cost/net-value explanation. Semantic assessment uses the frozen criteria and code-agent review, not the running LLM grading itself. No numerical mismatch was found in completed analyses.

Audit: `runs/real-repairs-v3-audit/audit.json`.

Direct invariant, transport, scope, routing and retained-allowance checks: **45 passed in 1.62 seconds**. These checks invoke no mock LLM. The transport deadline check exercises the actual child-process timeout; endpoint rejection and nested tool-network denial are also checked. The earlier full mock-based suite was not rerun or presented as live evidence in this task. Compilation and whitespace checks also completed.

## Accounting and limits

- New task, receipted cost: **USD 0.0080195069**.
- Four new unresolved requests: **USD 0.0446780832 reserved**, not counted as free.
- New task conservative accounting: **USD 0.0526975901**.
- Whole-project conservative accounting, including prior spend and old unresolved reservations: **USD 1.3260259185**, inside the unchanged **USD 3** ceiling.

Receipts are checked for existence and hash before classifying spend as known. Unresolved reservations are not provider invoices or confirmed charges. Existing unknown billing still needs reconciliation. No cloud resources, new dependency or dataset was introduced. Process startup adds normal overhead to the HTTP deadline. Initial live planning can still fail; the original interrupted 24-case verification remains incomplete. These small diagnostic/development samples do not establish broad model reliability or scientific generalization.
