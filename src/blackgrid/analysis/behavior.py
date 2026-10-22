"""Bounded descriptive behavioral tools; protocol sprint08_behavior_v1.

Identifiers occur only in local rows. public_output is the model disclosure boundary.
"""
from __future__ import annotations

import hashlib
import json
import time

import networkx as nx
import numpy as np
import sklearn
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

VERSION = "behavior-v1.1"  # additive same-snapshot comparisons; numerical methods unchanged
SEED = 8
TOOLS = ("behavior_features", "behavior_clustering", "behavior_similarity", "behavior_anomalies")
FEATURES = (
    "log_sent", "log_received", "log_recipients", "log_senders",
    "active_bin_fraction", "reciprocal_fraction", "outgoing_fraction", "peak_bin_fraction",
)
LIMITATIONS = (
    "Descriptive observed-window profiles; not causal effects, verified social groups, or future predictions.",
    "Similarity and anomaly scores are not probabilities or significance tests.",
    "Missing observations and unequal exposure can change all three analyses; real labels are unavailable.",
)


class BehaviorTools:
    def __init__(self, events, graph: nx.Graph, start: int, end: int, *, timeout_s: float = 60):
        if end <= start or timeout_s <= 0:
            raise ValueError("invalid behavioral window or deadline")
        if len(graph) > 1000 or graph.number_of_edges() > 10000:
            raise ValueError("behavioral analysis exceeds 1000 nodes or 10000 pairs")
        self.deadline = time.monotonic() + timeout_s
        self.nodes = sorted(graph.nodes())
        selected = []
        for u, v, ts in events:
            if start <= ts < end:
                if not all(type(x) is int and x >= 0 for x in (u, v, ts)):
                    raise ValueError("behavior events require nonnegative integer fields")
                selected.append((u, v, ts))
                if len(selected) > 100000:
                    raise ValueError("behavioral analysis exceeds 100000 selected events")
            self._check()
        observed_nodes = {n for u, v, _ in selected for n in (u, v)}
        pairs = {tuple(sorted((u, v))) for u, v, _ in selected if u != v}
        if graph.is_directed() or graph.is_multigraph() or nx.number_of_selfloops(graph) or (
            observed_nodes != set(self.nodes) or pairs != {tuple(sorted(e)) for e in graph.edges()}
        ):
            raise ValueError("behavior event window does not match the selected graph projection")
        index = {node: i for i, node in enumerate(self.nodes)}
        count = np.zeros((len(self.nodes), 2), dtype=float)
        bins = np.zeros((len(self.nodes), 7), dtype=float)
        outgoing = [set() for _ in self.nodes]
        incoming = [set() for _ in self.nodes]
        for u, v, ts in selected:
            if u == v:
                continue
            i, j = index[u], index[v]
            count[i, 0] += 1
            count[j, 1] += 1
            b = min(6, (ts - start) * 7 // (end - start))
            bins[i, b] += 1
            bins[j, b] += 1
            outgoing[i].add(v)
            incoming[j].add(u)
        self.x = np.zeros((len(self.nodes), len(FEATURES)), dtype=float)
        for i in range(len(self.nodes)):
            total = count[i].sum()
            neighbors = outgoing[i] | incoming[i]
            self.x[i] = (
                *np.log1p(count[i]), np.log1p(len(outgoing[i])), np.log1p(len(incoming[i])),
                np.count_nonzero(bins[i]) / 7,
                len(outgoing[i] & incoming[i]) / len(neighbors) if neighbors else 0,
                count[i, 0] / total if total else 0,
                bins[i].max() / total if total else 0,
            )
        self.active = np.flatnonzero(np.linalg.norm(self.x, axis=1) > 0)
        # Only selected events affect this identity; later events cannot alter results or ties.
        fingerprint = hashlib.sha256(json.dumps([VERSION, start, end, sorted(selected)],
                                                separators=(",", ":")).encode()).hexdigest()
        self.base = {
            "version": VERSION, "seed": SEED, "evidence_level": "descriptive",
            "window": {"start": start, "end": end, "interval": "half_open"},
            "feature_names": list(FEATURES), "snapshot_sha256": fingerprint,
            "runtime": {"numpy": np.__version__, "sklearn": sklearn.__version__},
            "limitations": list(LIMITATIONS),
        }
        self.population = {"nodes": len(self.nodes), "nonzero_profiles": len(self.active),
                           "zero_profiles": len(self.nodes) - len(self.active),
                           "events": len(selected), "excluded_self_events": sum(u == v for u, v, _ in selected)}
        self._check()

    def _check(self):
        if time.monotonic() > self.deadline:
            raise ValueError("behavior tool deadline exceeded")

    def call(self, name: str) -> dict:
        if name not in TOOLS:
            raise ValueError("unknown behavioral tool")
        self._check()
        result = self.base | {"tool": name, "verdict": "supported", "summary": dict(self.population)}
        if name == "behavior_features":
            result |= {"method": "eight fixed directed-event features; seven equal-duration bins",
                       "rows": [dict(node=n, **dict(zip(FEATURES, self.x[i].tolist())))
                                for i, n in enumerate(self.nodes)]}
        else:
            result |= getattr(self, name.removeprefix("behavior_"))()
        self._check()
        return result

    def _abstain(self, reason: str, method: str) -> dict:
        return {"verdict": "abstain", "reason": reason, "method": method, "rows": []}

    def clustering(self) -> dict:
        method = "StandardScaler and KMeans(k=3, n_init=10, seed=8); nonzero profiles only"
        x = self.x[self.active]
        if len(x) < 6 or len(np.unique(x, axis=0)) < 3:
            return self._abstain("Need six nonzero profiles and three distinct profiles.", method)
        scaler = StandardScaler().fit(x)
        z = scaler.transform(x)
        # Limit BLAS/OpenMP parallelism for predictable bounded local calls.
        with threadpool_limits(limits=1):
            model = KMeans(n_clusters=3, n_init=10, random_state=SEED).fit(z)
            labels = model.labels_
            silhouette = float(silhouette_score(z, labels)) if 1 < len(set(labels)) < len(z) else None
        assigned = dict(zip(self.active, labels))
        clusters = [{"cluster": k, "size": int(sum(labels == k)),
                     "feature_means": dict(zip(FEATURES, x[labels == k].mean(axis=0).tolist()))}
                    for k in range(3)]
        return {"method": method, "summary": self.population | {"clusters": 3, "silhouette": silhouette,
                    "inertia": float(model.inertia_), "cluster_profiles": clusters},
                "scaling": {"mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist()},
                "rows": [{"node": n, "cluster": int(assigned[i]) if i in assigned else None}
                         for i, n in enumerate(self.nodes)]}

    def similarity(self) -> dict:
        method = "Cosine on L2-normalized nonnegative feature vectors; five other neighbors per nonzero profile"
        if len(self.active) < 2:
            return self._abstain("Need two nonzero profiles for similarity.", method)
        x = self.x[self.active]
        z = x / np.linalg.norm(x, axis=1)[:, None]
        with threadpool_limits(limits=1):
            similarity = np.clip(z @ z.T, 0, 1)
        rows = []
        for i, node_index in enumerate(self.active):
            order = sorted((j for j in range(len(x)) if j != i),
                           key=lambda j: (-float(similarity[i, j]), self.nodes[self.active[j]]))[:5]
            rows.extend({"node": self.nodes[node_index], "neighbor": self.nodes[self.active[j]],
                         "rank": rank, "cosine": float(similarity[i, j])} for rank, j in enumerate(order, 1))
            self._check()
        return {"method": method, "summary": self.population | {"neighbor_rows": len(rows),
                    "max_similarity": max(r["cosine"] for r in rows)}, "rows": rows}

    def anomalies(self) -> dict:
        method = "Maximum absolute robust deviation; median/MAD with fixed scale floors; candidate cutoff 3.5"
        x = self.x[self.active]
        if len(x) < 20 or len(np.unique(x, axis=0)) < 2:
            return self._abstain("Need twenty nonzero, nonidentical profiles.", method)
        center = np.median(x, axis=0)
        scale = np.maximum(1.4826 * np.median(np.abs(x - center), axis=0), [1] * 4 + [.1] * 4)
        deviations = np.abs(x - center) / scale
        scores = deviations.max(axis=1)
        baseline = deviations[:, :2].max(axis=1)
        rows = [{"node": self.nodes[index], "score": float(scores[i]), "candidate": bool(scores[i] >= 3.5),
                 "count_baseline_score": float(baseline[i]), "count_baseline_candidate": bool(baseline[i] >= 3.5),
                 "strongest_feature": FEATURES[int(np.argmax(deviations[i]))]}
                for i, index in enumerate(self.active)]
        rows.sort(key=lambda row: (-row["score"], row["node"]))
        return {"method": method, "summary": self.population | {
                    "candidates": int(sum(scores >= 3.5)), "max_deviation": float(scores.max()),
                    "count_baseline_candidates": int(sum(baseline >= 3.5)),
                    "candidate_overlap": int(sum((scores >= 3.5) & (baseline >= 3.5)))},
                "scaling": {"median": center.tolist(), "scale": scale.tolist(), "cutoff": 3.5}, "rows": rows}


def public_output(payload: dict) -> dict:
    """Allowlist, rather than just deleting known private keys, protects future local fields."""
    return {k: payload[k] for k in ("version", "seed", "evidence_level", "window", "feature_names",
            "snapshot_sha256", "runtime", "limitations", "tool", "verdict", "summary", "method", "reason") if k in payload}


def compare_clusters(clustering: dict, anomalies: dict) -> dict:
    """Join local memberships to candidate flags; only group aggregates are public."""
    if clustering.get("verdict") == "abstain" or anomalies.get("verdict") == "abstain":
        return anomalies
    if not clustering.get("snapshot_sha256") or clustering["snapshot_sha256"] != anomalies.get("snapshot_sha256"):
        raise ValueError("cannot compare behavioral artifacts from different snapshots")
    membership = {r["node"]: r["cluster"] for r in clustering["rows"]}
    rows = anomalies["rows"]
    active = {n for n, k in membership.items() if k is not None}
    if (len(membership) != len(clustering["rows"]) or len({r["node"] for r in rows}) != len(rows)
            or {r["node"] for r in rows} != active):
        raise ValueError("behavior comparison populations do not match")
    joined = [r | {"cluster": membership[r["node"]]} for r in rows]
    groups = []
    for k in sorted({membership[n] for n in active}):
        group = [r for r in joined if r["cluster"] == k]
        flagged = sum(r["candidate"] for r in group)
        baseline = sum(r["count_baseline_candidate"] for r in group)
        groups.append(dict(cluster=k, size=len(group), candidates=flagged,
                           count_baseline_candidates=baseline, candidate_fraction=flagged / len(group),
                           count_baseline_fraction=baseline / len(group)))
    # Keyed aggregates are citable by the existing scalar evidence flattener.
    return anomalies | {"rows": joined, "summary": anomalies["summary"] | {
        "cluster_comparison": {str(g["cluster"]): g for g in groups}}}
