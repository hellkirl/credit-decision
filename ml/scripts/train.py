#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict, cross_val_score

from credit.config import (
    CALIBRATOR_PATH, CV_FOLDS, FIGURES_DIR, METADATA_PATH, RANDOM_STATE, REPORTS_DIR,
)
from credit.data import prepare_dataset
from credit.evaluate import (
    coefficient_table,
    compute_metrics,
    plot_confusion,
    plot_roc,
    save_metrics,
)
from credit.features import train_test
from credit.model import build_model, save_model
from credit.threshold import apply_threshold, find_best_threshold_youden


def main() -> None:
    print("Loading and cleaning raw data…")
    df = prepare_dataset()
    print(f"  rows={len(df)}, good={(df['credit_risk'] == 1).sum()}, bad={(df['credit_risk'] == 0).sum()}")

    X_train, X_test, y_train, y_test = train_test(df)
    print(f"  train={len(X_train)}, test={len(X_test)}")

    # Метаданные формируются только по обучающей выборке.
    numeric_ranges = {
        feature: {
            "min": int(X_train[feature].min()),
            "max": int(X_train[feature].max()),
        }
        for feature in ("duration", "amount", "age")
    }
    categorical_features = [
        "purpose", "personal_status_sex", "other_debtors",
        "other_installment_plans", "housing", "people_liable",
        "telephone", "foreign_worker",
    ]
    categorical_values = {
        feature: sorted(int(value) for value in X_train[feature].dropna().unique())
        for feature in categorical_features
    }
    METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    METADATA_PATH.write_text(
        json.dumps({
            "numeric_ranges": numeric_ranges,
            "categorical_values": categorical_values,
        }, indent=2),
        encoding="utf-8",
    )
    print(f"  metadata: {METADATA_PATH}")

    pipeline = build_model()
    print(f"Cross-validating ({CV_FOLDS}-fold ROC-AUC)…")
    cv_scores = cross_val_score(
        pipeline,
        X_train,
        y_train,
        cv=CV_FOLDS,
        scoring="roc_auc",
        n_jobs=-1,
    )
    print(f"  CV ROC-AUC: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

    print("Fitting on training set…")
    pipeline.fit(X_train, y_train)

    # OOF predictions prevent the calibrator from learning on in-sample predictions.
    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    p_good_oof = cross_val_predict(
        build_model(), X_train, y_train, cv=cv, method="predict_proba", n_jobs=-1
    )[:, 1]
    pd_oof = np.clip(1.0 - p_good_oof, 1e-6, 1.0 - 1e-6)
    default_oof = 1 - y_train.to_numpy()
    logit_pd = np.log(pd_oof / (1.0 - pd_oof)).reshape(-1, 1)
    calibrator = LogisticRegression(C=1e6, max_iter=1000, random_state=RANDOM_STATE)
    calibrator.fit(logit_pd, default_oof)
    CALIBRATOR_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(calibrator, CALIBRATOR_PATH)
    print(f"  PD calibrator: {CALIBRATOR_PATH}")

    y_proba = pipeline.predict_proba(X_test)[:, 1]
    threshold = find_best_threshold_youden(y_test, y_proba)
    metrics = compute_metrics(y_test, y_proba, threshold=threshold)

    print("\nTest metrics (Youden threshold):")
    for key in ("threshold", "accuracy", "precision", "recall", "f1", "roc_auc"):
        print(f"  {key}: {metrics[key]:.4f}" if key != "threshold" else f"  {key}: {metrics[key]:.3f}")
    print(metrics["classification_report"])

    model_path = save_model(pipeline)
    metrics_path = save_metrics(metrics)
    roc_path = plot_roc(y_test, y_proba)
    cm_path = plot_confusion(y_test, apply_threshold(y_proba, threshold))

    coefs = coefficient_table(pipeline)
    coef_path = REPORTS_DIR / "coefficients.csv"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    coefs.to_csv(coef_path, index=False)

    print("Artifacts:")
    print(f"  model:        {model_path}")
    print(f"  metrics:      {metrics_path}")
    print(f"  coefficients: {coef_path}")
    print(f"  ROC curve:    {roc_path}")
    print(f"  confusion:    {cm_path}")
    print(f"\nTop positive coefficients (→ higher P(good)):")
    print(coefs.head(8).to_string(index=False))
    print(f"\nTop negative coefficients (→ lower P(good)):")
    print(coefs.tail(8).iloc[::-1].to_string(index=False))


if __name__ == "__main__":
    main()
