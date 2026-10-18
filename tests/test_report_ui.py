"""Day 10 report evidence checks and UI safety."""

from __future__ import annotations

import json

import networkx as nx

from blackgrid.report import Report, ReportItem, ReportSection, check_numbers
from blackgrid.ui import compute_layout, esc, write_run_page

E = "experiment_report.json#/primary/result/"


def report(*items: ReportItem) -> Report:
    return Report(title="t", case_id="c", condition="validated", status="completed", verdict="not_supported",
                  sections=(ReportSection(title="s", items=items),))


def test_number_check_catches_unsupported_numbers():
    evidence = {E + "observed_statistic": 0.5865, E + "p_value": 0.718}
    ok = report(ReportItem(kind="result", text="Q = 0.587, p = 0.718.", evidence=(E + "observed_statistic", E + "p_value")))
    assert check_numbers(ok, evidence) == []
    bad = report(ReportItem(kind="result", text="Q = 0.587 with 95% confidence.", evidence=(E + "observed_statistic",)))
    assert check_numbers(bad, evidence) == ["[s] ['95%'] in: Q = 0.587 with 95% confidence."]
    uncited = report(ReportItem(kind="text", text="About 42 groups exist."))
    assert check_numbers(uncited, evidence)
    dates_ok = report(ReportItem(kind="text", text="Window starts 2004-04-15T14:56:01Z under exp-v1.1."))
    assert check_numbers(dates_ok, evidence) == []


def test_layout_has_no_identifiers():
    graph = nx.relabel_nodes(nx.path_graph(12), {i: 555_000_111 + i for i in range(12)})
    layout = compute_layout(graph)
    assert "555000" not in json.dumps(layout)
    assert sorted(layout["degree"]) == sorted(d for _, d in graph.degree())


def test_run_page_escapes_untrusted_text(tmp_path):
    run_dir = tmp_path / "runs" / "r1"
    run_dir.mkdir(parents=True)
    hostile = '<script>alert("x")</script><img src=x onerror=alert(1)>'
    inv = {"case_id": "c", "condition": "validated", "status": "completed", "verdict": "not_supported",
           "cost": {"mode": "mock", "llm_calls": 1, "input_tokens": 1, "output_tokens": 1, "actual_usd": 0.0},
           "reported_claims": [{"text": hostile, "evidence_level": "descriptive", "evidence": []}],
           "critic_decisions": [], "llm_calls": [], "tool_calls": []}
    (run_dir / "investigation.json").write_text(json.dumps(inv), encoding="utf-8")
    html = write_run_page(run_dir).read_text(encoding="utf-8")
    # The snapshot embeds data as JSON with <, >, & escaped, so untrusted text cannot close the data
    # block or inject markup; the browser inserts it with textContent only.
    assert "<script>alert" not in html and "<img src=x" not in html and "</script><" not in html
    import re

    boot = re.search(r'<script type="application/json" id="bg-boot">(.*?)</script>', html, re.S).group(1)
    data = json.loads(boot)
    assert data["payload"]["investigation"]["reported_claims"][0]["text"] == hostile  # round-trips intact
    assert "innerHTML" not in html  # the template never parses data as HTML
    assert (tmp_path / "runs" / "index.html").is_file()
    assert esc("<b>") == "&lt;b&gt;"
