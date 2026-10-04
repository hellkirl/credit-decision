from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

from credit.config import FIGURES_DIR, REPORTS_DIR
from credit.threshold import apply_threshold


def compute_metrics(
    y_true,
    y_proba: np.ndarray,
    threshold: float = 0.5,
) -> dict:
    y_pred = apply_threshold(y_proba, threshold)
    return {
        "threshold": threshold,
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_proba)),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
        "classification_report": classification_report(
            y_true,
            y_pred,
            target_names=["bad", "good"],
            zero_division=0,
        ),
    }


def plot_roc(y_true, y_proba: np.ndarray, path: Path | None = None) -> Path:
    path = path or (FIGURES_DIR / "roc_curve.png")
    path.parent.mkdir(parents=True, exist_ok=True)

    fpr, tpr, _ = roc_curve(y_true, y_proba)
    auc = roc_auc_score(y_true, y_proba)

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(fpr, tpr, label=f"Logistic regression (AUC = {auc:.3f})")
    ax.plot([0, 1], [0, 1], "k--", label="Chance")
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title("ROC — South German Credit")
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_confusion(
    y_true,
    y_pred: np.ndarray,
    path: Path | None = None,
) -> Path:
    path = path or (FIGURES_DIR / "confusion_matrix.png")
    path.parent.mkdir(parents=True, exist_ok=True)

    cm = confusion_matrix(y_true, y_pred)
    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(cm, cmap="Blues")
    ax.figure.colorbar(im, ax=ax)
    ax.set_xticks([0, 1], labels=["bad", "good"])
    ax.set_yticks([0, 1], labels=["bad", "good"])
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title("Confusion matrix")
    for (i, j), val in np.ndenumerate(cm):
        ax.text(j, i, str(val), ha="center", va="center", color="black")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def save_metrics(metrics: dict, path: Path | None = None) -> Path:
    path = path or (REPORTS_DIR / "metrics.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {k: v for k, v in metrics.items() if k != "classification_report"}
    path.write_text(json.dumps(payload, indent=2))
    report_path = path.with_name("classification_report.txt")
    report_path.write_text(metrics["classification_report"])
    return path


def coefficient_table(pipeline, feature_names: list[str] | None = None) -> pd.DataFrame:
    model = pipeline.named_steps["model"]
    preprocess = pipeline.named_steps["preprocess"]
    if feature_names is None:
        feature_names = list(preprocess.get_feature_names_out())
    coefs = model.coef_.ravel()
    return (
        pd.DataFrame({"feature": feature_names, "coefficient": coefs})
        .assign(odds_ratio=lambda d: np.exp(d["coefficient"]))
        .sort_values("coefficient", ascending=False)
        .reset_index(drop=True)
    )
