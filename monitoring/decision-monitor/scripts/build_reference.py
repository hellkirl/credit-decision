#!/usr/bin/env python3
"""Строит эталонный профиль данных (reference.json) для мониторинга дрейфа.

Эталон — обучающая выборка (800 заявок), та же, на которой учились модель и
калибратор. С ним мониторинг сравнивает текущий поток заявок.

Что сохраняется:
  * распределение каждого из 20 признаков модели (доли по корзинам);
  * распределение калиброванного PD. PD считается out-of-fold (5 фолдов),
    ровно как в scripts/train.py при обучении калибратора: так эталон PD
    честный, а не завышенно уверенный, как прогноз модели на своих же данных;
  * средний PD и доля дефолтов в обучении — точка отсчёта для калибровки;
  * хеши файлов модели и калибратора — к какой версии модели относится эталон.

Дополнительно сохраняется demo_applications.csv — тестовая выборка (200 заявок)
с реальными исходами для демо-прогона (scripts/simulate_traffic.py).

Запуск (из корня репозитория, в окружении ML-сервиса — нужен scikit-learn
той же версии, что в ml/requirements.txt):

    ml/venv/bin/python monitoring/decision-monitor/scripts/build_reference.py

Перезапускать после каждого переобучения модели (scripts/train.py).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np

HERE = Path(__file__).resolve().parent
DEFAULT_ML_ROOT = HERE.parents[2] / "ml"
DEFAULT_OUT = HERE.parent / "reference"

N_NUMERIC_BINS = 10  # децили для числовых признаков и PD


def sha256_short(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def numeric_profile(values: np.ndarray) -> dict:
    """Границы корзин по децилям эталона и доли эталона в каждой корзине."""
    qs = np.quantile(values, np.linspace(0, 1, N_NUMERIC_BINS + 1)[1:-1])
    edges = sorted(set(float(q) for q in qs))
    # Корзины: (-inf, e1], (e1, e2], ..., (ek, +inf)
    idx = np.digitize(values, edges, right=True)
    counts = np.bincount(idx, minlength=len(edges) + 1)
    return {
        "type": "numeric",
        "edges": edges,
        "expected": (counts / counts.sum()).tolist(),
    }


def categorical_profile(values: np.ndarray) -> dict:
    cats, counts = np.unique(values.astype(int), return_counts=True)
    return {
        "type": "categorical",
        "categories": cats.tolist(),
        "expected": (counts / counts.sum()).tolist(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ml-root", type=Path, default=DEFAULT_ML_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    sys.path.insert(0, str(args.ml_root / "src"))
    from sklearn.model_selection import StratifiedKFold, cross_val_predict

    from credit.config import (
        CALIBRATOR_PATH, CATEGORICAL_FEATURES, CV_FOLDS, FEATURE_COLUMNS,
        MODEL_PATH, NUMERIC_FEATURES, ORDINAL_FEATURES, RANDOM_STATE,
    )
    from credit.data import load_processed
    from credit.features import train_test
    from credit.model import build_model

    df = load_processed()
    X_train, X_test, y_train, y_test = train_test(df)  # то же разбиение 800/200, что в train.py

    # --- PD эталона: out-of-fold + сохранённый калибратор -----------------
    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    p_good_oof = cross_val_predict(
        build_model(), X_train, y_train, cv=cv, method="predict_proba"
    )[:, 1]
    pd_raw = np.clip(1.0 - p_good_oof, 1e-6, 1 - 1e-6)
    calibrator = joblib.load(CALIBRATOR_PATH)
    pd_cal = calibrator.predict_proba(np.log(pd_raw / (1 - pd_raw)).reshape(-1, 1))[:, 1]

    profile: dict = {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "ml/data/processed/south_german_credit.csv, обучающая выборка 800 "
                  f"(train_test, random_state={RANDOM_STATE})",
        "model_sha256": sha256_short(MODEL_PATH),
        "calibrator_sha256": sha256_short(CALIBRATOR_PATH),
        "n": int(len(X_train)),
        "train_default_rate": float((y_train == 0).mean()),  # target 1 = good
        "train_pd_mean": float(pd_cal.mean()),
        "pd": numeric_profile(pd_cal),
        "features": {},
    }
    for col in FEATURE_COLUMNS:
        values = X_train[col].to_numpy()
        if col in NUMERIC_FEATURES:
            profile["features"][col] = numeric_profile(values.astype(float))
        elif col in ORDINAL_FEATURES or col in CATEGORICAL_FEATURES:
            profile["features"][col] = categorical_profile(values)

    args.out.mkdir(parents=True, exist_ok=True)
    ref_path = args.out / "reference.json"
    ref_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

    # --- Демо-заявки: тест 200 с исходами ----------------------------------
    demo = X_test.copy()
    demo["credit_risk"] = y_test.to_numpy()
    demo_path = args.out / "demo_applications.csv"
    demo.to_csv(demo_path, index=False)

    print(f"reference:  {ref_path}")
    print(f"  model {profile['model_sha256']}, calibrator {profile['calibrator_sha256']}")
    print(f"  доля дефолтов в обучении {profile['train_default_rate']:.3f}, "
          f"средний PD (OOF, калиброванный) {profile['train_pd_mean']:.3f}")
    print(f"demo:       {demo_path} ({len(demo)} заявок)")


if __name__ == "__main__":
    main()
