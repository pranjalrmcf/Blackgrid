"""Session 4: bounded L2 logistic regression over historical features (SPRINT_06.md §6, stage 3).

Fixed grid C in {0.1, 1, 10}, 200-iteration cap, no class reweighting, no threshold search.
Scaling is fitted on supervised development rows only. Nonconvergence = failed configuration.
Outputs are uncalibrated ranking scores, never probabilities shown to users.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from blackgrid.prediction.features import Snapshot
from blackgrid.prediction.temporal import MAX_CANDIDATES, Task

GRID = (0.1, 1.0, 10.0)
MAX_ITER = 200
STRUCTURAL = ("common_neighbors", "jaccard", "adamic_adar", "resource_allocation", "preferential_attachment")
COUNTS = {"common_neighbors", "preferential_attachment", "deg_sum", "deg_product", "act_H_sum", "act_H_product",
          "pair_count", "recency_s"}  # nonnegative counts -> log1p
MAX_TRAINING_ROWS = MAX_CANDIDATES  # 2M labelled supervised rows across development snapshots (§5)


def feature_names(task: Task) -> tuple[str, ...]:
    base = STRUCTURAL + ("deg_sum", "deg_product", "act_H_sum", "act_H_product")
    return base + (("pair_count", "recency_s", "recency_unseen") if task == "repeat_pair" else ())


def design(snap: Snapshot, names: tuple[str, ...]) -> np.ndarray:
    cols = [np.log1p(snap.columns[c]) if c in COUNTS else snap.columns[c] for c in names]
    return np.column_stack(cols)


class TrainingCapacityExceeded(RuntimeError):
    pass


@dataclass
class Fitted:
    task: Task
    c: float
    names: tuple[str, ...]
    scaler: StandardScaler
    model: LogisticRegression
    converged: bool
    iterations: int

    def score(self, snap: Snapshot) -> np.ndarray:
        return self.model.decision_function(self.scaler.transform(design(snap, self.names)))


def fit(task: Task, training: list[Snapshot], c: float) -> Fitted:
    rows = sum(s.size for s in training)
    if rows > MAX_TRAINING_ROWS:
        raise TrainingCapacityExceeded(f"{task}: {rows} supervised rows > cap {MAX_TRAINING_ROWS}; not sampled")
    names = feature_names(task)
    x = np.vstack([design(s, names) for s in training])
    y = np.concatenate([s.labels for s in training])
    if y.all() or not y.any():
        raise ValueError("training rows need both classes")
    scaler = StandardScaler().fit(x)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        model = LogisticRegression(C=c, max_iter=MAX_ITER, solver="lbfgs").fit(scaler.transform(x), y)
    converged = not any(issubclass(w.category, ConvergenceWarning) for w in caught)
    return Fitted(task=task, c=c, names=names, scaler=scaler, model=model, converged=converged,
                  iterations=int(np.max(model.n_iter_)))
