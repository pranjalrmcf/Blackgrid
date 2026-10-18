"""Synthetic temporal event streams with known generating structure (development only, never CollegeMsg).

`triadic_stream` grows a network in which most new pairs close triangles and most events repeat
recent pairs, so structural and temporal methods both have real signal. Deterministic per seed.
"""
from __future__ import annotations

import random

from blackgrid.prediction.temporal import Event


def triadic_stream(seed: int = 1, nodes: int = 60, events: int = 3_000, start: int = 1_000_000,
                   step: int = 600, p_new_node: float = 0.03, p_repeat: float = 0.6,
                   p_triadic: float = 0.8) -> list[Event]:
    rng = random.Random(seed)
    active = [0, 1, 2]
    neighbours: dict[int, set[int]] = {0: {1}, 1: {0, 2}, 2: {1}}
    recent: list[tuple[int, int]] = [(0, 1), (1, 2)]
    out: list[Event] = [(0, 1, start), (1, 2, start + step)]
    t = start + step
    next_node = 3
    while len(out) < events:
        t += rng.randint(1, 2 * step)
        if next_node < nodes and rng.random() < p_new_node:  # a node is born, linking to an existing one
            u, v = next_node, rng.choice(active)
            active.append(u)
            next_node += 1
        elif rng.random() < p_repeat and recent:  # repeat a recent pair
            u, v = rng.choice(recent[-50:])
            if rng.random() < 0.5:
                u, v = v, u
        else:
            u = rng.choice(active)
            if rng.random() < p_triadic and neighbours.get(u):
                via = rng.choice(sorted(neighbours[u]))
                options = sorted(neighbours.get(via, set()) - neighbours[u] - {u})  # a genuinely new pair
                v = rng.choice(options) if options else rng.choice(active)
            else:
                v = rng.choice(active)
            if u == v:
                continue
        neighbours.setdefault(u, set()).add(v)
        neighbours.setdefault(v, set()).add(u)
        recent.append((u, v))
        out.append((u, v, t))
    return out
