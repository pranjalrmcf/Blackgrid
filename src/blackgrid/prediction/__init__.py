"""Sprint 6 baseline-first temporal link prediction (SPRINT_06.md; protocols/sprint06_prediction_v1.md).

Known-node, undirected, fixed-horizon pair forecasting. History is strictly before a cutoff `t`;
labels come from `[t, t + H)`. Sender/recipient roles are discarded for the pair task. No
GNN, no new dependencies: deterministic heuristics and metrics in pure Python.
"""

PREDICTION_VERSION = "prediction-v1"
