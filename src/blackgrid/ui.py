"""Console snapshots for runs, pilots, and the run index (wrappers around `blackgrid.console`).

Every finished run saves the interactive console as a static, offline snapshot (`report.html`)
with its data embedded; `blackgrid console` serves the same template live. The network layout is
computed here in pure Python: positions only, no identifiers. Node colours encode degree only,
never a community partition.
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
                "rejected": "bad", "failed": "bad", "partial": "warn", "paused": "warn", "running": "neutral",
                "cancelled": "bad", "denied": "bad", "budget_exhausted": "bad"}


def badge(verdict: str) -> str:
    return f'<span class="badge {VERDICT_TONE.get(verdict, "neutral")}">{esc(verdict).replace("_", " ")}</span>'


# --- layout (pure Python Fruchterman-Reingold; positions only, no identifiers) ------------------


LAYOUT_MAX_NODES = 5_000  # the full-dataset node cap (exp-v2-full)
EXACT_LAYOUT_MAX_NODES = 300  # above this, repulsion uses the grid approximation


def compute_layout(graph: nx.Graph, seed: int = 42) -> dict | None:
    """Largest component fills the top of the frame; smaller pieces sit in a strip below it."""
    n = graph.number_of_nodes()
    if n == 0 or n > LAYOUT_MAX_NODES:
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
    """Fruchterman-Reingold on one component, normalised to [0, 1] in both axes.

    Up to EXACT_LAYOUT_MAX_NODES every pair repels (unchanged, so small drawings are identical).
    Larger components use the grid variant from Fruchterman & Reingold (1991): nodes only repel
    neighbours within 2k, found through a grid of 2k cells, so each iteration is roughly linear.
    """
    n = len(order)
    if n == 1:
        return [(0.5, 0.5)]
    index = {node: i for i, node in enumerate(order)}
    pos = [[rng.uniform(-1, 1), rng.uniform(-1, 1)] for _ in order]
    edges = [(index[u], index[v]) for u, v in graph.edges()]
    k = math.sqrt(4.0 / n)
    temp = 0.2
    exact = n <= EXACT_LAYOUT_MAX_NODES
    if not exact:
        iterations = min(iterations, 80)
    for _ in range(iterations):
        disp = [[0.0, 0.0] for _ in order]
        if exact:
            pairs = ((i, j) for i in range(n) for j in range(i + 1, n))
        else:
            pairs = _grid_pairs(pos, 2 * k)
        for i, j in pairs:
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


def _grid_pairs(pos: list[list[float]], radius: float):
    """Index pairs closer than `radius`, using a grid of `radius`-sized cells (each pair once)."""
    cells: dict[tuple[int, int], list[int]] = {}
    for i, (x, y) in enumerate(pos):
        cells.setdefault((int(x // radius), int(y // radius)), []).append(i)
    r2 = radius * radius
    for (cx, cy), members in cells.items():
        for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1), (1, -1)):  # half the neighbourhood: no duplicates
            other = cells.get((cx + dx, cy + dy))
            if other is None:
                continue
            same = dx == 0 and dy == 0
            for a_pos, a in enumerate(members):
                ax, ay = pos[a]
                for b in (members[a_pos + 1:] if same else other):
                    ddx, ddy = ax - pos[b][0], ay - pos[b][1]
                    if ddx * ddx + ddy * ddy < r2:
                        yield a, b


# --- SVG components -----------------------------------------------------------------------------


def runs_root(folder: Path) -> Path:
    """The runs directory that holds `folder` (pilot sub-runs live one level deeper)."""
    parent = folder.parent
    return parent.parent if parent.name.startswith("pilot-") else parent


def write_run_page(run_dir: Path, graph: nx.Graph | None = None) -> Path:
    """Save this run's console snapshot (and refresh the index). Computes the layout if a graph is given."""
    from blackgrid.console.render import write_index_snapshot, write_run_snapshot

    if graph is not None:
        (run_dir / "layout.json").write_bytes(json.dumps(compute_layout(graph)).encode("utf-8"))
    root = runs_root(run_dir)
    out = write_run_snapshot(root, run_dir)
    write_index_snapshot(root)
    return out


def write_pilot_page(pilot_dir: Path) -> Path:
    from blackgrid.console.render import write_index_snapshot, write_pilot_snapshot

    out = write_pilot_snapshot(pilot_dir.parent, pilot_dir)
    write_index_snapshot(pilot_dir.parent)
    return out


def write_index(runs_dir: Path) -> Path:
    from blackgrid.console.render import write_index_snapshot

    return write_index_snapshot(runs_dir)
