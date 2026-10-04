from __future__ import annotations

import numpy as np
from sklearn.metrics import f1_score, roc_curve


def find_best_threshold_youden(y_true, y_proba: np.ndarray) -> float:
    fpr, tpr, thresholds = roc_curve(y_true, y_proba)
    j = tpr - fpr
    return float(thresholds[int(np.argmax(j))])


def find_best_threshold_f1(y_true, y_proba: np.ndarray) -> float:
    candidates = np.linspace(0.05, 0.95, 37)
    scores = [f1_score(y_true, (y_proba >= t).astype(int)) for t in candidates]
    return float(candidates[int(np.argmax(scores))])


def apply_threshold(y_proba: np.ndarray, threshold: float = 0.5) -> np.ndarray:
    return (np.asarray(y_proba) >= threshold).astype(int)
