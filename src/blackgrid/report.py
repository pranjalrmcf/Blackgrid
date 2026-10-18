"""Evidence-linked Markdown report (Sprint 1 Day 10).

The report is a list of items. Every `result` and `claim` item carries the artifact paths it
relies on, and `check_numbers` verifies that each number in its text equals one of those values
at the displayed precision. `text` items must contain no numbers at all unless they cite evidence.
`reference` items (citations, commands, hashes) are exempt and contain no findings.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from blackgrid.agent import InvestigationResult
from blackgrid.contracts import Contract, DataOrigin, GraphRecord, NonEmpty
from blackgrid.critic import mislabelled_numbers, unsupported_numbers

ItemKind = Literal["result", "claim", "text", "reference"]


class ReportItem(Contract):
    kind: ItemKind
    text: NonEmpty
    evidence: tuple[NonEmpty, ...] = ()
    label: str | None = None  # evidence level for claims


class ReportSection(Contract):
    title: NonEmpty
    items: tuple[ReportItem, ...]


class Report(Contract):
    title: NonEmpty
    case_id: NonEmpty
    condition: NonEmpty
    status: NonEmpty
    verdict: NonEmpty
    sections: tuple[ReportSection, ...]


def _get(evidence: dict[str, object], path: str) -> object:
    return evidence.get(path)


def build_report(result: InvestigationResult, evidence: dict[str, object], record: GraphRecord, question: str,
                 run_id: str, reproduce: str) -> Report:
    ev = evidence
    E = "experiment_report.json#/"
    S = "sensitivity.json#/"
    G = "graph_record.json#/"
    I = "investigation.json#/"
    sections: list[ReportSection] = []

    status_items = [ReportItem(kind="text", text=f"Condition: {result.condition}. Run status: {result.status.value}.")]
    if result.verdict in ("supported", "not_supported", "inconclusive", "abstain") and E + "verdict" in ev:
        label = ("Exploratory verdict (exp-v2-full rule, not preregistered)" if record.scope == "full_dataset"
                 else "Preregistered verdict")
        status_items.append(ReportItem(kind="result", evidence=(E + "verdict",),
                                       text=f"{label}: {ev[E + 'verdict']} (evidence level: descriptive; "
                                            "applies to this graph only)."))
    elif result.condition == "tool_only":
        status_items.append(ReportItem(kind="text", text=f"Analyst-stated verdict (not validated): {result.verdict}."))
    else:
        status_items.append(ReportItem(kind="text", text=f"Outcome: {result.verdict}."))
    if result.missing_analyses and result.verdict != "rejected":
        status_items.append(ReportItem(kind="text", text=(
            "PARTIAL ANSWER: the required analyses " + ", ".join(result.missing_analyses) + " did not run, so this "
            "report answers only part of the question.")))
    if result.failure_reason:
        status_items.append(ReportItem(kind="reference", text=f"Reason: {result.failure_reason}"))
    if result.plan_decision and not result.plan_decision.allowed:
        for reason in result.plan_decision.reasons:
            status_items.append(ReportItem(kind="reference", text=f"Refused before execution: {reason}"))
    sections.append(ReportSection(title="Outcome", items=tuple(status_items)))
    sections.append(ReportSection(title="Question", items=(
        ReportItem(kind="reference", text=f"> {question}"),
        ReportItem(kind="text", text="The question is treated as untrusted data; it cannot change tools or settings."),
    )))

    data_items = []
    full = record.scope == "full_dataset"
    if record.origin is DataOrigin.REAL_PUBLIC:
        data_items += [
            ReportItem(kind="result", evidence=(G + "window_events", G + "raw_events"),
                       text=(f"Full dataset: all {ev.get(G + 'window_events')} valid message events are used "
                             "(no time window)." if full else
                             f"Selected window holds {ev.get(G + 'window_events')} of {ev.get(G + 'raw_events')} "
                             "valid message events.")),
            ReportItem(kind="result", evidence=(G + "active_nodes", G + "unique_edges", G + "self_loop_events_excluded"),
                       text=f"Projected undirected graph: {ev.get(G + 'active_nodes')} active users, "
                            f"{ev.get(G + 'unique_edges')} unique pairs; {ev.get(G + 'self_loop_events_excluded')} "
                            "self-loop events excluded."),
            ReportItem(kind="text", text=(
                "Exploratory full-dataset analysis (exp-v2-full), versioned separately from the preregistered "
                "first-week experiment; the whole recording period is pooled into one static graph. Direction, "
                "message counts, and timing are discarded by design." if full else
                "Window chosen by the frozen size-only rule before any analysis; direction, "
                "message counts, and timing are discarded by design.")),
        ]
    else:
        data_items.append(ReportItem(kind="text", text="Synthetic development case. Generator details are "
                                                       "evaluator-only and are not shown to the agent or here."))
    sections.append(ReportSection(title="Data", items=tuple(data_items)))

    results = []
    if E + "primary/result/observed_statistic" in ev and ev[E + "primary/result/observed_statistic"] is not None:
        P = E + "primary/"
        results += [
            ReportItem(kind="result", evidence=(P + "result/observed_statistic", P + "result/null/mean",
                                                P + "result/null/sd", P + "result/null_replicates"),
                       text=f"Observed modularity Q = {ev[P + 'result/observed_statistic']:.3f}; degree-preserving null "
                            f"mean {ev[P + 'result/null/mean']:.3f} (sd {ev[P + 'result/null/sd']:.3f}) over "
                            f"{ev[P + 'result/null_replicates']} randomizations."),
            ReportItem(kind="result", evidence=(P + "result/null/q05", P + "result/null/q95"),
                       text=f"Null 5th-95th percentile range: {ev[P + 'result/null/q05']:.3f} to "
                            f"{ev[P + 'result/null/q95']:.3f}."),
            ReportItem(kind="result", evidence=(P + "delta_q",) + ((P + "z",) if ev.get(P + "z") is not None else ()),
                       text=f"Effect contrast: delta Q = {ev[P + 'delta_q']:.3f}"
                            + (f", z = {ev[P + 'z']:.2f} (descriptive)." if ev.get(P + "z") is not None else ".")),
            ReportItem(kind="result", evidence=(P + "result/p_value", P + "result/exceedances",
                                                P + "result/null_replicates"),
                       text=f"Monte Carlo p = {ev[P + 'result/p_value']:.3f} ({ev[P + 'result/exceedances']} of "
                            f"{ev[P + 'result/null_replicates']} null values at or above the observed value)."),
        ]
        if ev.get(E + "secondary/result/p_value") is not None:
            Sx = E + "secondary/"
            results.append(ReportItem(kind="result", evidence=(Sx + "nodes", Sx + "result/observed_statistic",
                                                               Sx + "result/null/mean", Sx + "result/p_value"),
                                      text=f"Largest component ({ev[Sx + 'nodes']} nodes): Q = "
                                           f"{ev[Sx + 'result/observed_statistic']:.3f} vs null mean "
                                           f"{ev[Sx + 'result/null/mean']:.3f}, p = {ev[Sx + 'result/p_value']:.3f}."))
    elif E + "primary/unsuitable_reasons" in ev or E + "verdict" in ev:
        results.append(ReportItem(kind="text", text="The experiment abstained: the graph failed a preregistered "
                                                    "suitability rule (see run artifacts)."))
    else:
        results.append(ReportItem(kind="text", text="No experiment result was produced."))
    sections.append(ReportSection(title="Experiment (exp-v2-full, exploratory)" if full else "Experiment (exp-v1.1)",
                                  items=tuple(results)))

    if S + "replicates" in ev:
        sections.append(ReportSection(title="Missing-edge sensitivity", items=(
            ReportItem(kind="result", evidence=(S + "removal_fraction", S + "replicates", S + "null_replicates_per_run",
                                                S + "agreement", S + "main_raw_verdict"),
                       text=f"Removing {ev[S + 'removal_fraction'] * 100:.0f}% of edges uniformly at random "
                            f"({ev[S + 'replicates']} replicates, {ev[S + 'null_replicates_per_run']} nulls each): "
                            f"{ev[S + 'agreement']} of {ev[S + 'replicates']} raw verdicts matched "
                            f"'{ev[S + 'main_raw_verdict']}'."),
            ReportItem(kind="result", evidence=(S + "observed_q_min", S + "observed_q_max"),
                       text=f"Observed Q across reduced graphs ranged {ev[S + 'observed_q_min']:.3f} to "
                            f"{ev[S + 'observed_q_max']:.3f}.") if ev.get(S + "observed_q_min") is not None else
            ReportItem(kind="text", text="No reduced graph produced a modularity value."),
            ReportItem(kind="text", text="Removed pairs are recorded as unknown, not as non-links. This is a "
                                         "sensitivity analysis under an assumed mechanism, not an uncertainty interval."),
        )))

    claim_items = [ReportItem(kind="claim", text=c.get("text", "")[:500] or "(empty)",
                              evidence=tuple(p for p in c.get("evidence", []) if isinstance(p, str)),
                              label=str(c.get("evidence_level")))
                   for c in result.reported_claims if isinstance(c, dict)]
    if not claim_items:
        claim_items = [ReportItem(kind="text", text="No claims passed review; the report states only the "
                                                    "preregistered outcome above.")]
    title = "Accepted claims (critic-reviewed)" if result.condition == "validated" else "Claims (NOT validated)"
    sections.append(ReportSection(title=title, items=tuple(claim_items)))

    rejected = [d for d in result.critic_decisions if not d.accepted]
    if rejected:
        sections.append(ReportSection(title="Rejected draft claims (kept visible)", items=tuple(
            ReportItem(kind="reference", text=f"\"{str(d.claim.get('text', ''))[:200]}\" - {'; '.join(d.reasons)}")
            for d in rejected)))

    limits = [ReportItem(kind="text", text=FLAG_TEXT[f]) for f in result.flags if f in FLAG_TEXT]
    limits += [ReportItem(kind="text", text=t) for t in (
        "No claim here is causal, predictive, or about real social groups; modularity is a structural statistic.",
        "Pseudonymous identifiers only; no individual is profiled and no raw records leave this machine.",
    )]
    if record.origin is DataOrigin.REAL_PUBLIC and full:
        limits += [ReportItem(kind="text", text=t) for t in (
            "Exploratory, not confirmatory: the first-week result and full-file descriptive counts were seen before "
            "this protocol was written.",
            "Pooling the whole recording period into one static graph merges ties formed at different times; it "
            "describes the aggregate network, not any moment in it.",
            "The missing-edge sensitivity uses fewer replicates than the first-week experiment, for runtime.",
            "Findings apply to the observed, projected messaging network only, not to unobserved users.")]
    elif record.origin is DataOrigin.REAL_PUBLIC:
        limits.append(ReportItem(kind="text", text="Findings apply only to the observed, projected window, not to "
                                                   "the full dataset or to unobserved users."))
    sections.append(ReportSection(title="Flags and limitations", items=tuple(limits)))

    sections.append(ReportSection(title="Prediction", items=(ReportItem(
        kind="reference", text="No predictive model exists in Sprint 1 (graph prediction is gated to Phase 3). "
                          "Nothing in this report is a prediction."),)))

    sections.append(ReportSection(title="Run accounting", items=(
        ReportItem(kind="result", evidence=(I + "cost/llm_calls", I + "cost/input_tokens", I + "cost/output_tokens",
                                            I + "cost/actual_usd"),
                   text=f"LLM calls {ev.get(I + 'cost/llm_calls')}, tokens in {ev.get(I + 'cost/input_tokens')}, "
                        f"tokens out {ev.get(I + 'cost/output_tokens')}, actual cost USD "
                        f"{ev.get(I + 'cost/actual_usd', 0):.4f} (mode {ev.get(I + 'cost/mode')})."),
        ReportItem(kind="reference", text=f"Run {run_id}; generated {datetime.now(UTC).isoformat(timespec='seconds')}."),
        ReportItem(kind="reference", text=f"Reproduce: `{reproduce}`"),
    )))
    if record.origin is DataOrigin.REAL_PUBLIC and record.source:
        sections.append(ReportSection(title="Data citation", items=tuple(
            ReportItem(kind="reference", text=c) for c in record.source.citations)))
    return Report(title=f"BLACKGRID investigation - {result.case_id}", case_id=result.case_id,
                  condition=result.condition, status=result.status.value, verdict=result.verdict,
                  sections=tuple(sections))


FLAG_TEXT = {
    "disconnected": "The graph is disconnected; separate components inflate modularity, so the largest component "
                    "was analysed separately.",
    "degree_confound": "Degree is highly uneven (hubs); hubs inflate raw modularity, which is why the comparison "
                       "uses a degree-preserving null.",
    "incomplete_observation": "Some node pairs are unobserved (unknown, not non-links); a 'supported' result is "
                              "downgraded to 'inconclusive' under exp-v1.1 rule A.",
    "causal_not_identified": "A causal question or claim was refused: no estimand, intervention, or identification "
                             "argument exists for this observational graph.",
    "invalid_method": "A requested method was not allowlisted and was refused before execution.",
}


def check_numbers(report: Report, evidence: dict[str, object]) -> list[str]:
    """Every number in result/claim/text items must match cited evidence. Returns violations."""
    problems = []
    for section in report.sections:
        for item in section.items:
            if item.kind == "reference":
                continue
            cited = {p: evidence[p] for p in item.evidence if p in evidence}
            bad = unsupported_numbers(item.text, list(cited.values())) + mislabelled_numbers(item.text, cited)
            if bad:
                problems.append(f"[{section.title}] {bad} in: {item.text[:120]}")
    return problems


def render_markdown(report: Report) -> str:
    lines = [f"# {report.title}", ""]
    for section in report.sections:
        lines += [f"## {section.title}", ""]
        for item in section.items:
            prefix = f"**[{item.label}]** " if item.kind == "claim" and item.label else ""
            cite = f"  <sub>evidence: {', '.join(f'`{p}`' for p in item.evidence)}</sub>" if item.evidence else ""
            lines.append(f"- {prefix}{item.text}{cite}" if item.kind != "reference" or not item.text.startswith(">")
                         else item.text)
        lines.append("")
    return "\n".join(lines)
