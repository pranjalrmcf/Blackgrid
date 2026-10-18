"""Static, offline "investigation console" pages generated from run artifacts.

No server, no external assets, no JavaScript dependencies: each page is a single self-contained
HTML file in the run directory. Everything shown is read from the stored artifacts; LLM text and
any other artifact text is HTML-escaped because it is untrusted. Node identifiers are never shown,
and node colours encode degree only, never a community partition.
"""

from __future__ import annotations

import html
import json
import math
import random
from pathlib import Path

import networkx as nx

# --- small helpers ------------------------------------------------------------------------------


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def fmt(value: object, digits: int = 3) -> str:
    if isinstance(value, bool) or value is None:
        return "—" if value is None else str(value)
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return esc(value)


def _load(run_dir: Path, name: str) -> dict | None:
    path = run_dir / name
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


VERDICT_TONE = {"supported": "ok", "not_supported": "neutral", "inconclusive": "warn", "abstain": "warn",
                "rejected": "bad", "failed": "bad", "partial": "warn"}


def badge(verdict: str) -> str:
    return f'<span class="badge {VERDICT_TONE.get(verdict, "neutral")}">{esc(verdict).replace("_", " ")}</span>'


# --- layout (pure Python Fruchterman-Reingold; positions only, no identifiers) ------------------


def compute_layout(graph: nx.Graph, seed: int = 42) -> dict | None:
    """Largest component fills the top of the frame; smaller pieces sit in a strip below it."""
    n = graph.number_of_nodes()
    if n == 0 or n > 400:
        return None
    rng = random.Random(seed)
    nodes = list(graph.nodes())
    rng.shuffle(nodes)  # index order carries no identifier information
    index = {node: i for i, node in enumerate(nodes)}
    comps = sorted((sorted(c, key=index.get) for c in nx.connected_components(graph)), key=len, reverse=True)
    points: list[list[float]] = [[0.0, 0.0] for _ in nodes]
    main_h = 0.78 if len(comps) > 1 else 1.0
    for (x, y), node in zip(_fr(graph.subgraph(comps[0]), comps[0], rng), comps[0]):
        points[index[node]] = [x, y * main_h]
    small = comps[1:]
    per_row = max(1, min(len(small), 12))
    cell = 1.0 / per_row
    for i, comp in enumerate(small):
        row, col = divmod(i, per_row)
        for (x, y), node in zip(_fr(graph.subgraph(comp), comp, rng, iterations=60), comp):
            points[index[node]] = [col * cell + cell * (0.2 + 0.6 * x), 0.86 + row * 0.1 + 0.08 * y]
    edges = [(index[u], index[v]) for u, v in graph.edges()]
    ys = [p[1] for p in points]
    top = max(ys) or 1.0
    return {"points": [[round(x, 4), round(y / top, 4)] for x, y in points],
            "degree": [graph.degree(node) for node in nodes], "edges": edges,
            "components": len(comps)}


def _fr(graph: nx.Graph, order: list, rng: random.Random, iterations: int = 120) -> list[tuple[float, float]]:
    """Fruchterman-Reingold on one component, normalised to [0, 1] in both axes."""
    n = len(order)
    if n == 1:
        return [(0.5, 0.5)]
    index = {node: i for i, node in enumerate(order)}
    pos = [[rng.uniform(-1, 1), rng.uniform(-1, 1)] for _ in order]
    edges = [(index[u], index[v]) for u, v in graph.edges()]
    k = math.sqrt(4.0 / n)
    temp = 0.2
    for _ in range(iterations):
        disp = [[0.0, 0.0] for _ in order]
        for i in range(n):
            for j in range(i + 1, n):
                dx, dy = pos[i][0] - pos[j][0], pos[i][1] - pos[j][1]
                d = math.hypot(dx, dy) or 1e-6
                f = k * k / d
                disp[i][0] += dx / d * f
                disp[i][1] += dy / d * f
                disp[j][0] -= dx / d * f
                disp[j][1] -= dy / d * f
        for a, b in edges:
            dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
            d = math.hypot(dx, dy) or 1e-6
            f = d * d / k
            disp[a][0] -= dx / d * f
            disp[a][1] -= dy / d * f
            disp[b][0] += dx / d * f
            disp[b][1] += dy / d * f
        for i in range(n):
            d = math.hypot(*disp[i]) or 1e-6
            step = min(d, temp)
            pos[i][0] += disp[i][0] / d * step
            pos[i][1] += disp[i][1] / d * step
        temp *= 0.97
    xs, ys = [p[0] for p in pos], [p[1] for p in pos]
    sx, sy = (max(xs) - min(xs)) or 1.0, (max(ys) - min(ys)) or 1.0
    return [((x - min(xs)) / sx, (y - min(ys)) / sy) for x, y in pos]


# --- SVG components -----------------------------------------------------------------------------


def network_svg(layout: dict | None) -> str:
    if not layout:
        return '<p class="muted">Graph too large to draw (over 400 nodes) or empty.</p>'
    w, h, pad = 560, 440, 22
    pts = [(pad + x * (w - 2 * pad), pad + y * (h - 2 * pad)) for x, y in layout["points"]]
    max_deg = max(layout["degree"]) or 1
    lines = "".join(f'<line x1="{pts[a][0]:.1f}" y1="{pts[a][1]:.1f}" x2="{pts[b][0]:.1f}" y2="{pts[b][1]:.1f}"/>'
                    for a, b in layout["edges"])
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{2.2 + 5 * math.sqrt(d / max_deg):.1f}" '
        f'style="fill:var(--{"hub" if d / max_deg > 0.45 else "node"})"><title>degree {d}</title></circle>'
        for (x, y), d in zip(pts, layout["degree"]))
    return (f'<svg class="net" viewBox="0 0 {w} {h}" role="img" aria-label="Network layout">'
            f'<g class="edges">{lines}</g><g>{dots}</g></svg>'
            '<p class="caption">Force-directed layout. Dot size and colour show degree (hubs glow brighter); '
            'colours are <b>not</b> communities. No identifiers are shown.</p>')


def histogram_svg(values: list[float], observed: float | None, q05: float | None = None, q95: float | None = None,
                  label: str = "null modularity") -> str:
    if not values:
        return '<p class="muted">No null distribution (the analysis abstained or did not run).</p>'
    w, h, pad_l, pad_b = 560, 220, 40, 34
    lo = min(values + ([observed] if observed is not None else []))
    hi = max(values + ([observed] if observed is not None else []))
    lo, hi = lo - (hi - lo) * 0.08 - 1e-9, hi + (hi - lo) * 0.08 + 1e-9
    bins = 30
    counts = [0] * bins
    for v in values:
        counts[min(int((v - lo) / (hi - lo) * bins), bins - 1)] += 1
    top = max(counts) or 1
    bw = (w - pad_l - 10) / bins
    x_of = lambda v: pad_l + (v - lo) / (hi - lo) * (w - pad_l - 10)
    bars = "".join(f'<rect x="{pad_l + i * bw + 1:.1f}" y="{h - pad_b - c / top * (h - pad_b - 16):.1f}" '
                   f'width="{bw - 2:.1f}" height="{c / top * (h - pad_b - 16):.1f}"/>' for i, c in enumerate(counts))
    band = ""
    if q05 is not None and q95 is not None:
        band = (f'<rect class="band" x="{x_of(q05):.1f}" y="8" width="{x_of(q95) - x_of(q05):.1f}" '
                f'height="{h - pad_b - 8}"/>')
    marker = ""
    if observed is not None:
        x = x_of(observed)
        marker = (f'<line class="obs" x1="{x:.1f}" y1="6" x2="{x:.1f}" y2="{h - pad_b}"/>'
                  f'<text class="obs-label" x="{min(x + 6, w - 120):.1f}" y="18">observed {observed:.3f}</text>')
    ticks = "".join(f'<text class="tick" x="{x_of(lo + (hi - lo) * t):.1f}" y="{h - 12}" text-anchor="middle">'
                    f'{lo + (hi - lo) * t:.3f}</text>' for t in (0.1, 0.5, 0.9))
    return (f'<svg class="hist" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)} histogram">{band}'
            f'<g class="bars">{bars}</g>{marker}<line class="axis" x1="{pad_l}" y1="{h - pad_b}" x2="{w - 10}" '
            f'y2="{h - pad_b}"/>{ticks}</svg>'
            f'<p class="caption">{len(values)} {esc(label)} values; shaded band = 5th–95th percentile; '
            'magenta line = observed graph.</p>')


def strip_svg(runs: list[dict], main_q: float | None) -> str:
    qs = [r["observed_q"] for r in runs if r.get("observed_q") is not None]
    if not qs:
        return '<p class="muted">No sensitivity replicates.</p>'
    w, h, pad = 560, 120, 40
    lo, hi = min(qs + ([main_q] if main_q else [])), max(qs + ([main_q] if main_q else []))
    lo, hi = lo - (hi - lo) * 0.1 - 1e-9, hi + (hi - lo) * 0.1 + 1e-9
    x_of = lambda v: pad + (v - lo) / (hi - lo) * (w - 2 * pad)
    dots = "".join(f'<circle class="{ "agree" if r["raw_verdict"] == runs[0].get("_main") else "v-" + r["raw_verdict"]}"'
                   f' cx="{x_of(r["observed_q"]):.1f}" cy="{50 + (i % 5) * 9 - 18}" r="5"><title>replicate '
                   f'{r["index"]}: Q {r["observed_q"]:.3f}, p {fmt(r.get("p_value"))}, {esc(r["raw_verdict"])}'
                   f'</title></circle>' for i, r in enumerate(runs) if r.get("observed_q") is not None)
    marker = (f'<line class="obs" x1="{x_of(main_q):.1f}" y1="10" x2="{x_of(main_q):.1f}" y2="{h - 30}"/>'
              if main_q is not None else "")
    ticks = "".join(f'<text class="tick" x="{x_of(lo + (hi - lo) * t):.1f}" y="{h - 8}" text-anchor="middle">'
                    f'{lo + (hi - lo) * t:.3f}</text>' for t in (0.1, 0.5, 0.9))
    return (f'<svg class="strip" viewBox="0 0 {w} {h}" role="img" aria-label="Sensitivity replicates">{marker}'
            f'{dots}<line class="axis" x1="{pad}" y1="{h - 26}" x2="{w - pad}" y2="{h - 26}"/>{ticks}</svg>'
            '<p class="caption">Each dot is one reduced graph (edges removed at random); magenta line = full graph. '
            'Hover for details.</p>')


def meter(label: str, used: float, cap: float, unit: str = "") -> str:
    frac = 0 if cap <= 0 else min(used / cap, 1)
    shown = f"{used:.4f}" if isinstance(used, float) and unit == "USD" else f"{used:g}"
    return (f'<div class="meter"><div class="meter-head"><span>{esc(label)}</span>'
            f'<span class="mono">{esc(shown)} / {cap:g} {esc(unit)}</span></div>'
            f'<div class="meter-track"><div class="meter-fill" style="width:{frac * 100:.1f}%"></div></div></div>')


def kv(rows: list[tuple[str, object]]) -> str:
    return '<dl class="kv">' + "".join(f"<dt>{esc(k)}</dt><dd>{fmt(v)}</dd>" for k, v in rows) + "</dl>"


# --- page shell ---------------------------------------------------------------------------------

CSS = """
:root{--bg:#04060c;--panel:#0a1020cc;--line:#1d2a44;--text:#d8e4ff;--muted:#7f8fb3;--cyan:#3ef0ff;--magenta:#ff3ecf;
--lime:#7dff9a;--amber:#ffc43e;--red:#ff5470;--node:#4d7cff;--hub:#3ef0ff;color-scheme:dark}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--text)}
body{font:14px/1.55 "Segoe UI",system-ui,-apple-system,sans-serif;min-height:100vh;padding:0 16px 48px;
background-image:linear-gradient(rgba(62,240,255,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(62,240,255,.045) 1px,transparent 1px);
background-size:36px 36px}
body:before{content:"";position:fixed;inset:0;pointer-events:none;background:radial-gradient(ellipse at 20% -10%,rgba(62,240,255,.14),transparent 55%),
radial-gradient(ellipse at 110% 10%,rgba(255,62,207,.10),transparent 50%)}
.wrap{max-width:1240px;margin:0 auto;position:relative}
header{display:flex;flex-wrap:wrap;align-items:center;gap:14px 24px;padding:26px 0 18px;border-bottom:1px solid var(--line)}
.brand{font:700 13px/1 ui-monospace,"Cascadia Code",Consolas,monospace;letter-spacing:.32em;color:var(--cyan);text-shadow:0 0 14px rgba(62,240,255,.6)}
.brand small{display:block;margin-top:6px;letter-spacing:.18em;color:var(--muted);font-weight:400}
h1{font-size:22px;margin:0;font-weight:600;letter-spacing:.02em;flex:1 1 320px}
h2{font:600 12px/1 ui-monospace,Consolas,monospace;letter-spacing:.24em;text-transform:uppercase;color:var(--cyan);margin:0 0 14px;display:flex;gap:10px;align-items:center}
h2:before{content:"";width:8px;height:8px;background:var(--cyan);box-shadow:0 0 10px var(--cyan)}
.grid{display:grid;gap:16px;margin-top:18px;grid-template-columns:repeat(12,minmax(0,1fr))}
.panel{grid-column:span 12;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:18px;position:relative;
backdrop-filter:blur(6px);box-shadow:0 0 0 1px rgba(62,240,255,.04),0 10px 30px rgba(0,0,0,.35)}
.panel:after{content:"";position:absolute;top:-1px;left:-1px;width:18px;height:18px;border-top:2px solid var(--cyan);border-left:2px solid var(--cyan);border-radius:6px 0 0 0}
@media(min-width:900px){.s4{grid-column:span 4}.s5{grid-column:span 5}.s6{grid-column:span 6}.s7{grid-column:span 7}.s8{grid-column:span 8}}
.badge{display:inline-block;padding:4px 12px;border-radius:999px;font:600 12px/1.4 ui-monospace,Consolas,monospace;letter-spacing:.12em;text-transform:uppercase;border:1px solid}
.badge.ok{color:var(--lime);border-color:var(--lime);box-shadow:0 0 12px rgba(125,255,154,.35)}
.badge.warn{color:var(--amber);border-color:var(--amber);box-shadow:0 0 12px rgba(255,196,62,.3)}
.badge.bad{color:var(--red);border-color:var(--red);box-shadow:0 0 12px rgba(255,84,112,.35)}
.badge.neutral{color:var(--cyan);border-color:var(--cyan);box-shadow:0 0 12px rgba(62,240,255,.3)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.stat{border:1px solid var(--line);border-radius:6px;padding:12px;background:rgba(62,240,255,.03)}
.stat b{display:block;font:600 24px/1.1 ui-monospace,Consolas,monospace;color:#fff;margin-top:4px}
.stat span{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
.mono,dd,code{font-family:ui-monospace,"Cascadia Code",Consolas,monospace}
.muted,.caption{color:var(--muted)}.caption{font-size:12px;margin:8px 0 0}
.kv{display:grid;grid-template-columns:max-content 1fr;gap:6px 18px;margin:0}.kv dt{color:var(--muted)}.kv dd{margin:0;overflow-wrap:anywhere}
svg{width:100%;height:auto;display:block}
.net .edges line{stroke:rgba(140,170,255,.28);stroke-width:1}.net circle{filter:drop-shadow(0 0 4px rgba(62,240,255,.5))}
.hist .bars rect{fill:rgba(62,240,255,.55)}.hist .band{fill:rgba(62,240,255,.07)}
.obs{stroke:var(--magenta);stroke-width:2.5;filter:drop-shadow(0 0 6px var(--magenta))}.obs-label{fill:var(--magenta);font:12px ui-monospace,Consolas,monospace}
.axis{stroke:var(--line)}.tick{fill:var(--muted);font:11px ui-monospace,Consolas,monospace}
.strip circle{fill:var(--cyan);opacity:.85}.strip circle.v-supported{fill:var(--lime)}.strip circle.v-abstain,.strip circle.v-inconclusive{fill:var(--amber)}
.timeline{list-style:none;margin:0;padding:0 0 0 18px;border-left:1px dashed var(--line)}
.timeline li{position:relative;padding:4px 0 12px 12px}.timeline li:before{content:"";position:absolute;left:-24px;top:10px;width:10px;height:10px;border-radius:50%;background:var(--bg);border:2px solid var(--cyan)}
.timeline li.fail:before{border-color:var(--red)}.timeline li.warn:before{border-color:var(--amber)}
.timeline .t{font:600 12px ui-monospace,Consolas,monospace;color:var(--cyan);letter-spacing:.08em}
.claim{border-left:3px solid var(--lime);padding:8px 12px;margin:8px 0;background:rgba(125,255,154,.04);border-radius:0 6px 6px 0}
.claim.rej{border-color:var(--red);background:rgba(255,84,112,.05)}.claim .why{color:var(--red);font-size:12px;margin-top:4px}
.claim .ev{color:var(--muted);font-size:11px;margin-top:4px;overflow-wrap:anywhere}
.meter{margin:10px 0}.meter-head{display:flex;justify-content:space-between;font-size:12px;color:var(--muted)}
.meter-track{height:6px;background:#111a2e;border-radius:6px;overflow:hidden;margin-top:4px}.meter-fill{height:100%;background:linear-gradient(90deg,var(--cyan),var(--magenta));box-shadow:0 0 10px var(--cyan)}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font:600 11px ui-monospace,Consolas,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
.tablewrap{overflow-x:auto}.yes{color:var(--lime)}.no{color:var(--red)}
a{color:var(--cyan)}a:hover{color:#fff}
.report h3{font-size:13px;color:var(--cyan);margin:16px 0 6px;letter-spacing:.06em}.report ul{margin:0;padding-left:18px}.report li{margin:4px 0}
.notice{border:1px dashed var(--amber);color:var(--amber);padding:10px 14px;border-radius:6px;font-size:13px}
.pulse{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--lime);box-shadow:0 0 10px var(--lime);animation:p 2s infinite}
@keyframes p{50%{opacity:.3}}
@media (prefers-reduced-motion:reduce){.pulse{animation:none}}
footer{margin-top:28px;color:var(--muted);font-size:12px;text-align:center}
"""


def page(title: str, heading: str, right: str, body: str) -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title>'
            f'<style>{CSS}</style></head><body><div class="wrap"><header><div class="brand">BLACKGRID'
            f'<small>// INVESTIGATION CONSOLE</small></div><h1>{heading}</h1><div>{right}</div></header>'
            f'{body}<footer>Generated offline from run artifacts. Mock outputs validate plumbing only. '
            f'No identifiers, no network, no external assets.</footer></div></body></html>')


# --- run page -----------------------------------------------------------------------------------


def write_run_page(run_dir: Path, graph: nx.Graph | None = None) -> Path:
    manifest = _load(run_dir, "manifest.json") or {}
    inv = _load(run_dir, "investigation.json") or {}
    exp = _load(run_dir, "experiment_report.json")
    sens = _load(run_dir, "sensitivity.json")
    record = _load(run_dir, "graph_record.json") or {}
    report = _load(run_dir, "report.json") or {}
    budget = _load(run_dir, "budget.json") or {}
    if graph is not None:
        layout = compute_layout(graph)
        (run_dir / "layout.json").write_bytes(json.dumps(layout).encode("utf-8"))
    layout = _load(run_dir, "layout.json")

    verdict = inv.get("verdict", "failed")
    status = manifest.get("status", inv.get("status", "?"))
    cost = inv.get("cost", {})
    mode = cost.get("mode", "?")
    right = (f'{badge(verdict)} <span class="muted mono" style="margin-left:10px">'
             f'<span class="pulse"></span> {esc(status)} · {esc(mode)} · {esc(inv.get("condition"))}</span>')
    blocks = []
    if inv.get("missing_analyses") and inv.get("verdict") != "rejected":
        blocks.append('<section class="panel"><div class="notice">PARTIAL ANSWER — required analyses did not run: '
                      f'{esc(", ".join(inv["missing_analyses"]))}. The question is only partly answered.</div>'
                      "</section>")
    if mode == "mock":
        blocks.append('<section class="panel"><div class="notice">MOCK MODE — the planner and analyst are scripted '
                      'stand-ins. Statistics are real; the "agent" text is not a model\'s output.</div></section>')

    primary = (exp or {}).get("primary") or {}
    res = primary.get("result") or {}
    null = res.get("null") or {}
    stats = [("Observed Q", res.get("observed_statistic")), ("Null mean", null.get("mean")),
             ("ΔQ", primary.get("delta_q")), ("z", primary.get("z")), ("p-value", res.get("p_value")),
             ("Nulls", res.get("null_replicates"))]
    blocks.append('<section class="panel s7"><h2>Experiment · modularity vs degree-preserving null</h2>'
                  '<div class="stats">' + "".join(f'<div class="stat"><span>{esc(k)}</span><b>{fmt(v)}</b></div>'
                                                  for k, v in stats) + '</div><div style="margin-top:16px">'
                  + histogram_svg(list(primary.get("null_values") or []), res.get("observed_statistic"),
                                  null.get("q05"), null.get("q95"))
                  + "</div>" + _secondary(exp) + "</section>")
    blocks.append('<section class="panel s5"><h2>Network · projected graph</h2>' + network_svg(layout) + "</section>")

    profile = (exp or {}).get("profile") or {}
    prov = [("Graph", record.get("graph_id")), ("Origin", record.get("origin")),
            ("Active nodes", record.get("active_nodes")), ("Unique edges", record.get("unique_edges")),
            ("Components", profile.get("components")), ("Max / median degree",
             f'{profile.get("degree_max", "—")} / {profile.get("degree_median", "—")}'),
            ("Window events", record.get("window_events")), ("Projection SHA-256",
             (record.get("projection_sha256") or "")[:16] + "…")]
    if record.get("source"):
        prov.insert(2, ("Dataset", record["source"].get("dataset_id")))
    blocks.append('<section class="panel s4"><h2>Provenance</h2>' + kv(prov) + "</section>")

    if sens:
        runs = list(sens.get("runs") or [])
        if runs:
            runs[0] = dict(runs[0], _main=sens.get("main_raw_verdict"))
        sstats = [("Removed", f'{sens.get("removal_fraction", 0) * 100:.0f}%'), ("Replicates", sens.get("replicates")),
                  ("Agreement", f'{sens.get("agreement")}/{sens.get("replicates")}'),
                  ("Main raw verdict", sens.get("main_raw_verdict"))]
        blocks.append('<section class="panel s8"><h2>Missing-edge sensitivity</h2><div class="stats">'
                      + "".join(f'<div class="stat"><span>{esc(k)}</span><b>{fmt(v)}</b></div>' for k, v in sstats)
                      + '</div><div style="margin-top:14px">' + strip_svg(runs, res.get("observed_statistic"))
                      + '</div><p class="caption">' + esc(sens.get("label")) + "</p></section>")
    else:
        blocks.append('<section class="panel s8"><h2>Missing-edge sensitivity</h2><p class="muted">Not run '
                      "(the plan did not include it, or the run stopped earlier).</p></section>")

    blocks.append('<section class="panel s6"><h2>Agent trace</h2>' + _timeline(inv) + "</section>")
    blocks.append('<section class="panel s6"><h2>Claims · critic review</h2>' + _claims(inv) + "</section>")
    blocks.append('<section class="panel s7"><h2>Report</h2><div class="report">' + _report_html(report)
                  + "</div></section>")
    limits = budget.get("limits", {})
    pricing = budget.get("pricing", {})
    blocks.append('<section class="panel s5"><h2>Budget</h2>'
                  + meter("LLM calls", cost.get("llm_calls", 0), limits.get("max_llm_calls", 8))
                  + meter("Tokens", cost.get("input_tokens", 0) + cost.get("output_tokens", 0),
                          limits.get("max_tokens", 20000))
                  + meter("Spend (this run)", float(cost.get("actual_usd", 0.0)),
                          limits.get("max_usd_per_investigation", 0.5), "USD")
                  + kv([("Provider pricing", pricing.get("source")), ("Model", pricing.get("model")),
                        ("Revisions", inv.get("revisions"))])
                  + '<h2 style="margin-top:22px">Prediction</h2><p class="muted">No predictive model exists in '
                    "Sprint 1 — graph prediction is gated to Phase 3. Nothing on this page is a prediction.</p>"
                  + "</section>")

    body = '<div class="grid">' + "".join(blocks) + "</div>"
    out = run_dir / "report.html"
    out.write_bytes(page(f"BLACKGRID · {inv.get('case_id', run_dir.name)}",
                         f"{esc(inv.get('case_id', ''))} <span class='muted mono' style='font-size:13px'>"
                         f"{esc(run_dir.name)}</span>", right, body).encode("utf-8"))
    write_index(run_dir.parent if not run_dir.parent.name.startswith("pilot-") else run_dir.parent.parent)
    return out


def _secondary(exp: dict | None) -> str:
    sec = (exp or {}).get("secondary")
    if not sec:
        return ""
    r = sec.get("result") or {}
    if not sec.get("suitable"):
        return (f'<p class="caption">Largest component ({fmt(sec.get("nodes"))} nodes): abstained — '
                f'{esc("; ".join(sec.get("unsuitable_reasons") or []))}</p>')
    return (f'<p class="caption">Largest component ({fmt(sec.get("nodes"))} nodes): Q {fmt(r.get("observed_statistic"))}'
            f' vs null mean {fmt((r.get("null") or {}).get("mean"))}, p {fmt(r.get("p_value"))}.</p>')


def _timeline(inv: dict) -> str:
    items = []
    calls = list(inv.get("llm_calls") or [])
    tools = list(inv.get("tool_calls") or [])
    plan = inv.get("plan") or {}
    if calls:
        c = calls[0]
        items.append(("planner", f'{"ok" if c.get("ok") else "failed"} · {c.get("prompt_tokens")}+'
                                 f'{c.get("completion_tokens")} tokens · plan: '
                                 + ", ".join(str(t.get("tool")) for t in plan.get("tool_calls", []) if isinstance(t, dict)),
                      "" if c.get("ok") else "fail"))
    decision = inv.get("plan_decision")
    if decision:
        items.append(("validator", ("allowed" if decision.get("allowed") else "REFUSED") + " · "
                      + "; ".join(decision.get("reasons") or []), "" if decision.get("allowed") else "warn"))
    elif inv.get("condition") == "tool_only":
        items.append(("validator", "disabled in tool_only condition", "warn"))
    main_tools = [t for t in tools if "[" not in t.get("tool", "")]
    reps = [t for t in tools if "[" in t.get("tool", "")]
    for t in main_tools:
        items.append((t.get("tool"), f'{t.get("outcome")} · {t.get("elapsed_s", 0):.2f}s'
                      + (" · cached" if t.get("cached") else "") + (f' · {t.get("error")}' if t.get("error") else ""),
                      "fail" if t.get("outcome") == "failed" else ""))
    if reps:
        items.append(("sensitivity replicates", f"{len(reps)} bounded calls · "
                      f"{sum(r.get('elapsed_s', 0) for r in reps):.1f}s total", ""))
    for c in calls[1:]:
        items.append((c.get("role"), f'{"ok" if c.get("ok") else "failed"} · {c.get("prompt_tokens")}+'
                      f'{c.get("completion_tokens")} tokens' + (f' · {c.get("error")}' if c.get("error") else ""),
                      "" if c.get("ok") else "fail"))
    decisions = inv.get("critic_decisions") or []
    if decisions:
        rej = sum(not d.get("accepted") for d in decisions)
        items.append(("critic", f"{len(decisions) - rej} accepted · {rej} rejected", "warn" if rej else ""))
    items.append(("outcome", f'{inv.get("status")} · verdict {inv.get("verdict")}'
                  + (f' · {inv.get("failure_reason")}' if inv.get("failure_reason") else ""),
                  "fail" if inv.get("status") == "failed" else ""))
    return '<ul class="timeline">' + "".join(
        f'<li class="{cls}"><div class="t">{esc(str(name).upper())}</div><div>{esc(text)}</div></li>'
        for name, text, cls in items) + "</ul>"


def _claims(inv: dict) -> str:
    out = []
    shown = {json.dumps(c, sort_keys=True) for c in inv.get("reported_claims") or []}
    for c in inv.get("reported_claims") or []:
        out.append(f'<div class="claim"><b>[{esc(c.get("evidence_level"))}]</b> {esc(c.get("text"))}'
                   f'<div class="ev">evidence: {esc(", ".join(map(str, c.get("evidence") or [])))}</div></div>')
    for d in inv.get("critic_decisions") or []:
        if not d.get("accepted") and json.dumps(d.get("claim"), sort_keys=True) not in shown:
            c = d.get("claim") or {}
            out.append(f'<div class="claim rej"><b>REJECTED</b> {esc(c.get("text"))}'
                       f'<div class="why">{esc("; ".join(d.get("reasons") or []))}</div></div>')
    if inv.get("condition") == "tool_only" and inv.get("reported_claims"):
        out.insert(0, '<p class="notice">tool_only condition: these claims were NOT reviewed.</p>')
    return "".join(out) or '<p class="muted">No claims were drafted.</p>'


def _report_html(report: dict) -> str:
    parts = []
    for section in report.get("sections", []):
        parts.append(f"<h3>{esc(section.get('title'))}</h3><ul>")
        for item in section.get("items", []):
            label = f"<b>[{esc(item.get('label'))}]</b> " if item.get("kind") == "claim" and item.get("label") else ""
            text = str(item.get("text") or "").removeprefix("> ")
            parts.append(f"<li>{label}{esc(text)}</li>")
        parts.append("</ul>")
    return "".join(parts) or '<p class="muted">No report.</p>'


# --- pilot page ---------------------------------------------------------------------------------


def write_pilot_page(pilot_dir: Path) -> Path:
    data = _load(pilot_dir, "pilot.json") or {}
    summary = data.get("summary", {})
    conditions = list(summary)
    head = "".join(f"<th>{esc(c)}</th>" for c in conditions)
    rows = "".join(f"<tr><td>{esc(m)}</td>" + "".join(f'<td class="mono">{fmt(summary[c][m], 4)}</td>'
                                                     for c in conditions) + "</tr>"
                   for m in (summary[conditions[0]] if conditions else {}))
    cases = "".join(
        f'<tr><td class="mono">{esc(r["case"])}</td><td>{esc(r["task"])}</td><td>{esc(r["condition"])}</td>'
        f'<td>{badge(r["verdict"])}</td><td class="{"yes" if r["verdict_ok"] else "no"}">{r["verdict_ok"]}</td>'
        f'<td class="{"yes" if r["flags_ok"] else "no"}">{r["flags_ok"]}</td><td class="mono">{r["unsupported_claims"]}'
        f'/{r["claims"]}</td><td><a href="{esc(r["run_dir"])}/report.html">open</a></td></tr>'
        for r in data.get("rows", []))
    body = (f'<section class="panel" style="margin-top:18px"><div class="notice">{esc(data.get("label"))}</div></section>'
            '<div class="grid"><section class="panel s6"><h2>Condition summary</h2><div class="tablewrap"><table>'
            f"<tr><th>metric</th>{head}</tr>{rows}</table></div></section>"
            '<section class="panel"><h2>Per case</h2><div class="tablewrap"><table><tr><th>case</th><th>task</th>'
            "<th>condition</th><th>verdict</th><th>verdict ok</th><th>flags ok</th><th>unsupported</th><th></th></tr>"
            f"{cases}</table></div></section></div>")
    out = pilot_dir / "pilot.html"
    out.write_bytes(page("BLACKGRID · pilot", f"Mock pilot <span class='muted mono' style='font-size:13px'>"
                         f"{esc(pilot_dir.name)}</span>", f'<span class="badge neutral">{esc(data.get("evaluator"))}'
                         "</span>", body).encode("utf-8"))
    write_index(pilot_dir.parent)
    return out


# --- index --------------------------------------------------------------------------------------


def write_index(runs_dir: Path) -> Path:
    rows = []
    for d in sorted((p for p in runs_dir.iterdir() if p.is_dir()), reverse=True):
        if (d / "pilot.html").is_file():
            data = _load(d, "pilot.json") or {}
            s = data.get("summary", {})
            rows.append(f'<tr><td class="mono"><a href="{esc(d.name)}/pilot.html">{esc(d.name)}</a></td><td>pilot</td>'
                        f'<td>{badge("mock")}</td><td class="mono">'
                        + esc(" · ".join(f"{c}: useful {v.get('useful_coverage')}" for c, v in s.items()))
                        + "</td></tr>")
        elif (d / "report.html").is_file():
            inv = _load(d, "investigation.json") or {}
            m = _load(d, "manifest.json") or {}
            rows.append(f'<tr><td class="mono"><a href="{esc(d.name)}/report.html">{esc(d.name)}</a></td>'
                        f'<td>{esc(inv.get("case_id"))}</td><td>{badge(inv.get("verdict", "failed"))}</td>'
                        f'<td class="mono">{esc(m.get("status"))} · {esc((inv.get("cost") or {}).get("mode"))} · '
                        f'{esc(inv.get("condition"))}</td></tr>')
    body = ('<section class="panel" style="margin-top:18px"><h2>Runs</h2><div class="tablewrap"><table>'
            "<tr><th>run</th><th>case</th><th>verdict</th><th>details</th></tr>" + "".join(rows)
            + "</table></div></section>")
    out = runs_dir / "index.html"
    out.write_bytes(page("BLACKGRID · runs", "Run index", f'<span class="muted mono">{len(rows)} runs</span>',
                         body).encode("utf-8"))
    return out
