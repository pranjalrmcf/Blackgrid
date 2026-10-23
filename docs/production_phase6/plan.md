# Phase 6 follow-up: live dashboard and concurrent-user benchmarks

The user authorized Phase 6 implementation on 23 October 2026 and explicitly excluded vLLM. The historical proposal below is superseded by the implemented [design](design.md), [operator guide](guide.md) and [execution report](report.md). Paid-provider load, cloud/GPU resources and later phases remain outside scope. Benchmark v2 is a protocol revision; the application image includes all previous phases.

## Dynamic dashboard

Extend the existing service with an authenticated browser dashboard that refreshes automatically. Prefer bounded polling every two to five seconds over adding another service. Reuse Phase 5 metrics and private job traces, show last-update time and stale/disconnected states, and preserve ordinary-owner versus global-operator access.

Provide browser authentication without embedding bearer tokens in HTML, URLs or browser local storage. Retain localhost HTTPS, origin protections and no-store behavior. Any browser session design must enforce expiry and protect state-changing requests. The current HTML snapshot remains available until the live view is implemented.

Show time-series charts for virtual users, request rate, accepted/rejected submissions, active jobs, queue depth/wait, API and end-to-end p50/p95/p99, completed analyses per minute, failures/cancellations, CPU/memory and LLM tokens/costs. Separate API, graph, agent, provider and complete-workflow views. Label mock versus real-provider runs, workload family/input scope, sample counts, measurement window, hardware and software revision. Keep benchmark samples separate from normal operational rolling snapshots so cache windows or capacity truncation cannot silently distort benchmark statistics.

Read measurements from actual benchmark records; never animate invented load. Scope job detail by ownership and exclude questions, raw events/identifiers, model content, secrets and arbitrary error strings. Export machine-readable reports and raw sanitized timing samples alongside charts. Benchmark generator resource use and dashboard polling overhead must be measured separately from target-server usage.

## Concurrent-user protocol

Freeze workloads, seeds, synthetic graph sizes, arrival patterns, durations, warmup, stopping criteria and resource budgets before execution. Begin with small stages such as 1, 5 and 10 virtual users; expand only when prior measurements and agreed resource limits permit it. The original larger stage suggestions are configurations to evaluate, not capacity promises.

Virtual users authenticate, submit with stable idempotency keys, poll, retrieve results and think before their next request. Report offered load, accepted load, completed throughput, queue-full responses, rate limits and failures separately. Concurrent clients do not imply concurrent analysis execution: the current service has one active worker and at most eight waiting jobs. Measure that boundary explicitly; do not raise worker/queue limits to hide saturation. Keep analytical correctness and budget-termination checks in the benchmark acceptance criteria.

Start offline with realistic mock schemas, token sizes, latency, retries and failure scenarios. Any hosted real-LLM benchmark requires separately explicit spending limits and authorization. Do not claim mocks measure actual provider speed or inference quality. Do not silently replace the configured real dataset with synthetic data or expand frozen scientific limits; benchmark inputs/configurations must be explicitly versioned and labeled.

## Historical vLLM proposal — superseded

The user subsequently directed that vLLM remain out of scope. The following explanatory proposal is retained as history; it authorizes no installation, backend comparison or infrastructure work in Phase 6.

The existing application calls hosted OpenRouter inference through its restricted broker. Adding vLLM to the BLACKGRID application image cannot optimize that remote backend or accelerate graph algorithms. vLLM is a potential self-hosted inference backend, not a switch applied to existing hosted requests.

Phase 6 should first separate graph runtime, queue wait, agent orchestration and provider time. If measurements justify self-hosting, prepare a separately approved backend comparison, with suitable hardware (usually a GPU), accessible/licensed model weights, fixed model revision/precision/settings, memory limits and total infrastructure cost. A different model must be treated as a new experimental condition with tool-selection, structured-output and scientific-claim quality checks; it is not an equivalent speed-only change.

vLLM offers continuous batching, KV-cache memory management and an OpenAI-compatible serving interface; see [official vLLM documentation](https://docs.vllm.ai/en/latest/) and [the serving implementation documentation](https://github.com/vllm-project/vllm/blob/main/docs/serving/online_serving/README.md). Compatibility with BLACKGRID still requires an explicit allowlisted provider/broker adapter, network containment, provenance and accounting design; do not loosen the existing OpenRouter-only broker or assume API compatibility makes it a drop-in change.

Do not install vLLM, download weights, rent hardware or change the approved model during this planning update. A backend trial can be proposed after bottleneck measurements; actual inference optimization belongs in the evidence-driven Phase 8 gate unless the user separately authorizes a bounded Phase 6 comparison. Streaming TTFT/throughput should only be reported if the tested interface exposes real measurements.

## Acceptance additions

- The browser updates from real measurements without manual HTML regeneration and visibly indicates stale data.
- Ordinary clients cannot see other owners' jobs or global operator data.
- Benchmark concurrency, admission, queueing and completions reconcile with durable job records.
- API and end-to-end latency distributions, resource usage, failures and costs are reproducible and separated by workload/mode.
- Monitoring does not trigger paid work, disclose credentials or change scientific/budget behavior.
- vLLM is explicitly excluded by the user's subsequent instruction; no inference-speed benefit is asserted.
