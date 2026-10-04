from __future__ import annotations

from pathlib import Path

import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from credit.config import MODEL_PATH, RANDOM_STATE
from credit.features import build_feature_pipeline


def build_model(
    C: float = 1.0,
    class_weight: str | dict | None = "balanced",
    max_iter: int = 1000,
    random_state: int = RANDOM_STATE,
) -> Pipeline:
    clf = LogisticRegression(
        C=C,
        solver="lbfgs",
        class_weight=class_weight,
        max_iter=max_iter,
        random_state=random_state,
    )
    return build_feature_pipeline(clf)


def save_model(pipeline: Pipeline, path: Path | None = None) -> Path:
    path = path or MODEL_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, path)
    return path


def load_model(path: Path | None = None) -> Pipeline:
    path = path or MODEL_PATH
    return joblib.load(path)
