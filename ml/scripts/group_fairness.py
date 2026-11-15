#!/usr/bin/env python3
"""Этап 5 — различия качества решения между группами.

Проверяет ФИНАЛЬНУЮ систему (как она работает в сервисе после Этапа 4):
  модель logistic_regression.joblib -> калибратор Платта -> три зоны по PD
  (approve < 0.083 <= review <= 0.285 < reject) -> бизнес-правила
  (YOUNG_APPLICANT_REVIEW: отказ клиенту <= 25 лет -> ручная проверка;
   неизвестная заявка: выход за диапазон / новая категория -> ручная проверка).

Что считает:
  1. Сверка: логика решения в скрипте = ответы ML API (прогон чувствительности, Этап 5).
  2. Качество по группам на тесте (200) — финальные артефакты из models/.
  3. То же на всех 1000 заявках out-of-fold: 5 фолдов, в каждом конвейер train.py
     обучается заново (модель + калибратор на OOF внутри фолда + метаданные),
     прогноз — только на отложенный фолд. Это даёт n в 5 раз больше теста.
  4. Бутстрэп разницы «группа минус остальные» (95% ДИ) — значимо или шум.
  5. Прокси-признаки: восстанавливается ли защищённая группа по остальным признакам.
  6. «Без защищённых признаков»: что будет с качеством и разрывами, если их убрать.
  7. Перекос интерфейса: код personal_status_sex=4 (жен. одна) интерфейс не передаёт.

Запуск из папки ml/:  python scripts/group_fairness.py
Результат: reports/group_fairness/stage5/
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from credit.config import (
    CALIBRATOR_PATH, CATEGORICAL_FEATURES, CV_FOLDS, FEATURE_COLUMNS, METADATA_PATH,
    MODEL_PATH, NUMERIC_FEATURES, ORDINAL_FEATURES, RANDOM_STATE, TARGET,
)
from credit.data import load_processed
from credit.features import train_test
from credit.model import build_model

OUT = ROOT / "reports" / "group_fairness" / "stage5"
FIG = OUT / "figures"
SENS_DIR = ROOT / "reports" / "sensitivity" / "stage5-first-run"

# --- Логика решения: копия credit/api.py (_validate_application + _predict_one) ---
APPROVE_PD = 0.083
REJECT_PD = 0.285
YOUNG_AGE = 25

# --- Методика Этапа 2/4 (границы зафиксированы до анализа) ---
AGE_BINS = [-np.inf, 25, 35, 50, np.inf]
AGE_LABELS = ["<=25", "26-35", "36-50", ">50"]
PSS_LABELS = {1: "муж. разведён", 2: "жен. не одна / муж. холост",
              3: "муж. женат/вдовец", 4: "жен. одна"}
FW_LABELS = {1: "иностранец", 2: "не иностранец"}
PROTECTED = ["age", "personal_status_sex", "foreign_worker"]
MIN_N = 30          # группы с n < 30 — без выводов
GAP_PP = 10.0       # критерий разбора: ложные отказы группы отличаются от среднего > 10 п.п.
N_BOOT = 2000


# ============================================================ решение =====
def validate(X: pd.DataFrame, meta: dict) -> pd.Series:
    """True = заявка неизвестная (как _validate_application в api.py)."""
    bad = pd.Series(False, index=X.index)
    for f, b in meta["numeric_ranges"].items():
        bad |= (X[f] < b["min"]) | (X[f] > b["max"])
    for f, allowed in meta["categorical_values"].items():
        bad |= ~X[f].isin(allowed)
    return bad


def calibrate(calibrator, p_good: np.ndarray) -> np.ndarray:
    pd_raw = np.clip(1.0 - p_good, 1e-6, 1.0 - 1e-6)
    logit = np.log(pd_raw / (1.0 - pd_raw)).reshape(-1, 1)
    return np.clip(calibrator.predict_proba(logit)[:, 1], 0.0, 1.0)


def decide(X: pd.DataFrame, pd_value: np.ndarray, unknown: pd.Series) -> pd.DataFrame:
    zone = np.where(pd_value < APPROVE_PD, "approve",
                    np.where(pd_value <= REJECT_PD, "review", "reject"))
    young_rule = (zone == "reject") & (X["age"].to_numpy() <= YOUNG_AGE)
    rec = np.where(young_rule, "review", zone)
    unk = unknown.to_numpy()
    rec = np.where(unk, "review", rec)
    return pd.DataFrame({
        "pd": np.where(unk, np.nan, pd_value),
        "pd_model": pd_value,                     # PD модели даже для неизвестных — для слоя «Модель»
        "pd_zone": np.where(unk, "unknown", zone),
        "recommendation": rec,
        "rule_young": young_rule & ~unk,
        "rule_unknown": unk,
    }, index=X.index)


def score(model, calibrator, meta, X: pd.DataFrame) -> pd.DataFrame:
    p_good = model.predict_proba(X[FEATURE_COLUMNS])[:, 1]
    return decide(X, calibrate(calibrator, p_good), validate(X, meta))


# ===================================================== конвейер train.py ====
def make_pipeline(features: list[str]) -> Pipeline:
    """Тот же конвейер, что build_model(), но с выбором признаков (для п. 6)."""
    if features == FEATURE_COLUMNS:
        return build_model()
    pre = ColumnTransformer([
        ("num", StandardScaler(), [f for f in NUMERIC_FEATURES if f in features]),
        ("ord", "passthrough", [f for f in ORDINAL_FEATURES if f in features]),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False),
         [f for f in CATEGORICAL_FEATURES if f in features]),
    ], remainder="drop")
    clf = LogisticRegression(solver="lbfgs", class_weight="balanced", max_iter=1000,
                             random_state=RANDOM_STATE)
    return Pipeline([("preprocess", pre), ("model", clf)])


def fit_like_train_py(X: pd.DataFrame, y: pd.Series, features: list[str]):
    """Повторяет train.py: модель на всём train + калибратор Платта на OOF + метаданные."""
    model = make_pipeline(features).fit(X[features], y)
    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    p_oof = cross_val_predict(make_pipeline(features), X[features], y, cv=cv,
                              method="predict_proba")[:, 1]
    pd_oof = np.clip(1.0 - p_oof, 1e-6, 1.0 - 1e-6)
    cal = LogisticRegression(C=1e6, max_iter=1000, random_state=RANDOM_STATE)
    cal.fit(np.log(pd_oof / (1 - pd_oof)).reshape(-1, 1), 1 - y.to_numpy())
    meta = {
        "numeric_ranges": {f: {"min": int(X[f].min()), "max": int(X[f].max())}
                           for f in ("duration", "amount", "age")},
        "categorical_values": {f: sorted(int(v) for v in X[f].unique())
                               for f in CATEGORICAL_FEATURES},
    }
    return model, cal, meta


def oof_scores(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    X, y = df[FEATURE_COLUMNS], df[TARGET]
    outer = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    parts = []
    for fold, (tr, te) in enumerate(outer.split(X, y)):
        model, cal, meta = fit_like_train_py(X.iloc[tr], y.iloc[tr], features)
        Xte = X.iloc[te]
        p_good = model.predict_proba(Xte[features])[:, 1]
        res = decide(Xte, calibrate(cal, p_good), validate(Xte, meta))
        res["fold"] = fold
        parts.append(res)
    return pd.concat(parts).loc[df.index]


# ============================================================ метрики =====
def wilson(k: float, n: float, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def add_groups(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["g_age"] = pd.cut(out["age"], bins=AGE_BINS, labels=AGE_LABELS).astype(str)
    out["g_pss"] = out["personal_status_sex"].map(PSS_LABELS)
    out["g_fw"] = out["foreign_worker"].map(FW_LABELS)
    return out


GROUPINGS = [("all", None), ("Возраст", "g_age"), ("Семейное положение/пол", "g_pss"),
             ("Иностранный работник", "g_fw")]


def group_rows(d: pd.DataFrame):
    yield "Все", "все", d
    for title, col in GROUPINGS[1:]:
        order = AGE_LABELS if col == "g_age" else (
            list(PSS_LABELS.values()) if col == "g_pss" else list(FW_LABELS.values()))
        for g in order:
            yield title, g, d[d[col] == g]


def metrics(g: pd.DataFrame) -> dict:
    n = len(g)
    bad = g["default"] == 1
    good = ~bad
    k = int(bad.sum())
    lo, hi = wilson(k, n)
    scored = g["pd"].notna()
    r = {
        "n": n, "n_bad": k, "n_good": int(good.sum()),
        "default_rate": k / n if n else np.nan, "default_ci_lo": lo, "default_ci_hi": hi,
        "pd_mean": g.loc[scored, "pd"].mean(),
        "calib_gap_pp": (g.loc[scored, "pd"].mean() - g.loc[scored, "default"].mean()) * 100,
        "auc": (roc_auc_score(g["default"], g["pd_model"])
                if k >= 5 and good.sum() >= 5 else np.nan),
        "brier": brier_score_loss(g["default"], g["pd_model"]) if n else np.nan,
        "share_approve": (g["recommendation"] == "approve").mean(),
        "share_review": (g["recommendation"] == "review").mean(),
        "share_reject": (g["recommendation"] == "reject").mean(),
        "share_rule_young": g["rule_young"].mean(),
        "share_unknown": g["rule_unknown"].mean(),
        # Слой «Модель»: хорошего клиента модель отправила в зону отказа
        "false_reject_zone": (g.loc[good, "pd_zone"] == "reject").mean() if good.any() else np.nan,
        # Слой «Решение»: хорошему клиенту итоговая рекомендация — отказ (как в мониторинге Этапа 4)
        "false_reject_decision": (g.loc[good, "recommendation"] == "reject").mean() if good.any() else np.nan,
        # Хорошие клиенты, ушедшие на ручную проверку (нагрузка на специалиста)
        "good_to_review": (g.loc[good, "recommendation"] == "review").mean() if good.any() else np.nan,
        # Плохой клиент автоматически одобрен
        "false_approve": (g.loc[bad, "recommendation"] == "approve").mean() if bad.any() else np.nan,
    }
    r["fr_zone_k"] = int((g.loc[good, "pd_zone"] == "reject").sum())
    r["enough"] = n >= MIN_N
    return r


def table(d: pd.DataFrame, sample: str) -> pd.DataFrame:
    rows = []
    for title, name, g in group_rows(d):
        rows.append({"sample": sample, "grouping": title, "group": name, **metrics(g)})
    t = pd.DataFrame(rows)
    base = t.iloc[0]
    for m in ("false_reject_zone", "false_reject_decision", "share_review", "good_to_review"):
        t[f"{m}_gap_pp"] = (t[m] - base[m]) * 100
    return t


def bootstrap_gaps(d: pd.DataFrame, seed: int = RANDOM_STATE) -> pd.DataFrame:
    """95% ДИ разницы «группа − остальные» по ключевым метрикам (перевыборка строк)."""
    rng = np.random.default_rng(seed)
    n = len(d)
    good = (d["default"] == 0).to_numpy()
    fr_zone = (d["pd_zone"] == "reject").to_numpy()
    fr_dec = (d["recommendation"] == "reject").to_numpy()
    review = (d["recommendation"] == "review").to_numpy()
    resid = (d["pd_model"] - d["default"]).to_numpy()
    rows = []
    for title, col in GROUPINGS[1:]:
        for g in d[col].unique():
            m = (d[col] == g).to_numpy()
            if m.sum() < MIN_N:
                continue
            stats = {k: [] for k in ("fr_zone", "fr_dec", "review", "calib")}

            def gap(idx):
                mm, gg = m[idx], good[idx]
                a, b = mm & gg, ~mm & gg
                return {
                    "fr_zone": fr_zone[idx][a].mean() - fr_zone[idx][b].mean(),
                    "fr_dec": fr_dec[idx][a].mean() - fr_dec[idx][b].mean(),
                    "review": review[idx][mm].mean() - review[idx][~mm].mean(),
                    "calib": resid[idx][mm].mean() - resid[idx][~mm].mean(),
                }
            point = gap(np.arange(n))
            for _ in range(N_BOOT):
                s = gap(rng.integers(0, n, n))
                for k in stats:
                    stats[k].append(s[k])
            for k, label in [("fr_zone", "ложные отказы, зона модели"),
                             ("fr_dec", "ложные отказы, итоговое решение"),
                             ("review", "доля ручной проверки"),
                             ("calib", "калибровка: PD − факт")]:
                arr = np.array(stats[k]) * 100
                lo, hi = np.nanpercentile(arr, [2.5, 97.5])
                rows.append({"grouping": title, "group": g, "metric": label,
                             "gap_pp": point[k] * 100, "ci_lo_pp": lo, "ci_hi_pp": hi,
                             "significant": bool(lo > 0 or hi < 0)})
    return pd.DataFrame(rows)


# ========================================================= прокси =========
def proxy_check(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Насколько защищённая группа восстанавливается по остальным признакам."""
    others = [f for f in FEATURE_COLUMNS if f not in PROTECTED]
    targets = {"возраст <= 25": (df["age"] <= 25).astype(int),
               "иностранец": (df["foreign_worker"] == 1).astype(int),
               "жен. одна (код 4)": (df["personal_status_sex"] == 4).astype(int)}
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    summary, top = [], []
    for name, t in targets.items():
        pipe = make_pipeline(others)
        p = cross_val_predict(pipe, df[others], t, cv=cv, method="predict_proba")[:, 1]
        summary.append({"target": name, "n_positive": int(t.sum()),
                        "auc_from_other_features": roc_auc_score(t, p)})
        # Какие признаки сильнее всего «выдают» группу: AUC признака в одиночку
        for f in others:
            enc = df[f].map(t.groupby(df[f]).mean()) if f not in NUMERIC_FEATURES else df[f]
            auc = roc_auc_score(t, enc)
            top.append({"target": name, "feature": f, "single_feature_auc": max(auc, 1 - auc)})
    top = (pd.DataFrame(top).sort_values(["target", "single_feature_auc"], ascending=[True, False])
           .groupby("target").head(4))
    return pd.DataFrame(summary), top


# ========================================================= графики ========
BLUE, ORANGE, INK, MUTED = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e"


def plot_slide(t: pd.DataFrame, path: Path) -> None:
    d = t[(t["group"] != "все") & t["enough"]].copy()
    d = d.iloc[::-1].reset_index(drop=True)
    base = t.iloc[0]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2), sharey=True,
                             gridspec_kw={"width_ratios": [1.15, 1]})
    y = np.arange(len(d))
    h = 0.36
    ax = axes[0]
    ax.barh(y + h / 2, d["false_reject_zone"] * 100, h, color=BLUE,
            label="модель (зона «отказ»)", edgecolor="white", linewidth=1.5)
    ax.barh(y - h / 2, d["false_reject_decision"] * 100, h, color=ORANGE,
            label="итоговое решение (после правил)", edgecolor="white", linewidth=1.5)
    ax.axvline(base["false_reject_zone"] * 100, color=MUTED, ls="--", lw=1)
    ax.text(base["false_reject_zone"] * 100 + 0.5, len(d) - 0.4,
            f"среднее {base['false_reject_zone']*100:.0f}%", color=MUTED, fontsize=9)
    for i, v in enumerate(d["false_reject_zone"] * 100):
        ax.text(v + 0.6, i + h / 2, f"{v:.0f}%", va="center", fontsize=8.5, color=INK)
    for i, (v, rule) in enumerate(zip(d["false_reject_decision"] * 100, d["share_rule_young"])):
        if v == 0 and rule > 0:
            ax.text(0.6, i - h / 2, "0% — все отказы ушли на ручную проверку",
                    va="center", fontsize=8.5, color=MUTED)
    ax.set_title("Ложные отказы: хороших клиентов → «отказ»", fontsize=11, loc="left", color=INK)
    ax.set_yticks(y, d["group"])
    fig.legend(*ax.get_legend_handles_labels(), loc="lower left", ncol=2, fontsize=9,
               frameon=False, bbox_to_anchor=(0.01, -0.01))
    ax = axes[1]
    ax.barh(y, d["share_review"] * 100, 0.55, color=BLUE, edgecolor="white", linewidth=1.5)
    ax.axvline(base["share_review"] * 100, color=MUTED, ls="--", lw=1)
    for i, v in enumerate(d["share_review"] * 100):
        ax.text(v + 0.6, i, f"{v:.0f}%", va="center", fontsize=8.5, color=INK)
    ax.set_title("Доля заявок на ручную проверку", fontsize=11, loc="left", color=INK)
    for ax in axes:
        ax.grid(axis="x", alpha=0.25)
        ax.set_xlabel("%", color=MUTED)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.tick_params(colors=MUTED)
    fig.suptitle("Финальная система, 1000 заявок out-of-fold. Группы с n < 30 не показаны",
                 fontsize=10, color=MUTED, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(path, dpi=170)
    plt.close(fig)


def plot_calibration(t: pd.DataFrame, path: Path) -> None:
    d = t[(t["group"] != "все") & t["enough"]].iloc[::-1].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(8, 5))
    y = np.arange(len(d))
    ax.hlines(y, d["default_ci_lo"] * 100, d["default_ci_hi"] * 100, color=MUTED, lw=2)
    ax.plot(d["default_rate"] * 100, y, "o", color=MUTED, ms=8, label="факт дефолтов (95% ДИ)")
    ax.plot(d["pd_mean"] * 100, y, "D", color=BLUE, ms=8, label="средний PD модели",
            markeredgecolor="white")
    ax.set_yticks(y, d["group"])
    ax.set_xlabel("%", color=MUTED)
    ax.set_title("Калибровка по группам: PD модели против факта", loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    ax.grid(axis="x", alpha=0.25)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)


# ============================================================ main ========
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    df = load_processed()
    df["default"] = 1 - df[TARGET]
    meta_info = {"sklearn": sklearn.__version__, "pandas": pd.__version__,
                 "numpy": np.__version__, "seed": RANDOM_STATE, "n_boot": N_BOOT,
                 "thresholds": {"approve_lt": APPROVE_PD, "reject_gt": REJECT_PD},
                 "young_rule_age_le": YOUNG_AGE, "min_group_n": MIN_N}

    # ---------- финальные артефакты ----------
    model = joblib.load(MODEL_PATH)
    calibrator = joblib.load(CALIBRATOR_PATH)
    meta = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    X_train, X_test, y_train, y_test = train_test(df)

    # 1a. Артефакты в models/ = результат train.py (воспроизводимость)
    m2, c2, _ = fit_like_train_py(X_train, y_train, FEATURE_COLUMNS)
    a = calibrate(calibrator, model.predict_proba(X_test)[:, 1])
    b = calibrate(c2, m2.predict_proba(X_test)[:, 1])
    meta_info["artifacts_vs_retrain_max_abs_pd_diff"] = float(np.abs(a - b).max())

    # 1b. Логика решения в скрипте = ответы ML API (прогон коллеги по чувствительности)
    check = {}
    sens = SENS_DIR / "sensitivity_results.csv"
    bases = SENS_DIR / "baselines.csv"
    if sens.exists() and bases.exists():
        b_df = pd.read_csv(bases).set_index("base_id")
        s_df = pd.read_csv(sens)
        s_df = s_df[s_df["scoring_status"] == "ok"]
        rows = []
        for _, r in s_df.iterrows():
            x = b_df.loc[r["base_id"], FEATURE_COLUMNS].copy()
            x[r["feature"]] = r["variant_value"]
            rows.append(x)
        V = pd.DataFrame(rows).astype(int).reset_index(drop=True)
        res = score(model, calibrator, meta, V)
        api_rec = s_df["variant_recommendation"].replace({"manual_review": "review"}).to_numpy()
        both = res["pd"].notna().to_numpy() & s_df["variant_pd"].notna().to_numpy()
        check = {"n_variants": int(len(V)),
                 "max_abs_pd_diff_vs_api": float(np.abs(res["pd"].to_numpy()[both]
                                                        - s_df["variant_pd"].to_numpy()[both]).max()),
                 "recommendation_mismatches_vs_api": int((res["recommendation"].to_numpy() != api_rec).sum())}
    meta_info["check_vs_ml_api"] = check

    # 2. Тест 200 — финальные артефакты как есть
    test = add_groups(df.loc[X_test.index])
    test = test.join(score(model, calibrator, meta, X_test))
    t_test = table(test, "test_200")

    # 3. OOF 1000 — финальный конвейер, переобученный по фолдам
    full = add_groups(df).join(oof_scores(df, FEATURE_COLUMNS))
    t_oof = table(full, "oof_1000")
    gq = pd.concat([t_oof, t_test], ignore_index=True)
    gq.to_csv(OUT / "group_quality_final.csv", index=False)
    full.to_csv(OUT / "oof_predictions.csv", index_label="row_id")

    # 4. Бутстрэп разрывов
    gaps = bootstrap_gaps(full)
    gaps.to_csv(OUT / "group_gaps_bootstrap.csv", index=False)

    # 5. Прокси
    proxy, proxy_top = proxy_check(df)
    proxy.to_csv(OUT / "proxy_check.csv", index=False)
    proxy_top.to_csv(OUT / "proxy_top_features.csv", index=False)

    # 6. Без защищённых признаков (те же фолды)
    variants = {"финальная (все 20 признаков)": FEATURE_COLUMNS,
                "без foreign_worker": [f for f in FEATURE_COLUMNS if f != "foreign_worker"],
                "без age, personal_status_sex, foreign_worker":
                    [f for f in FEATURE_COLUMNS if f not in PROTECTED]}
    unaware = []
    for name, feats in variants.items():
        v = full[["age", "g_age", "g_pss", "g_fw", "default"]].join(
            oof_scores(df, feats) if feats != FEATURE_COLUMNS else full[
                ["pd", "pd_model", "pd_zone", "recommendation", "rule_young", "rule_unknown"]])
        tv = table(v, name)
        row = {"variant": name, "n_features": len(feats),
               "auc": roc_auc_score(v["default"], v["pd_model"]),
               "brier": brier_score_loss(v["default"], v["pd_model"])}
        for g in ("<=25", "иностранец", "жен. одна", "жен. не одна / муж. холост"):
            r = tv[tv["group"] == g].iloc[0]
            row[f"fr_zone_gap_pp[{g}]"] = r["false_reject_zone_gap_pp"]
            row[f"calib_gap_pp[{g}]"] = r["calib_gap_pp"]
        row["share_review_all"] = tv.iloc[0]["share_review"]
        row["false_reject_zone_all"] = tv.iloc[0]["false_reject_zone"]
        unaware.append(row)
    pd.DataFrame(unaware).to_csv(OUT / "without_protected_features.csv", index=False)

    # 7. Перекос интерфейса: personal_status_sex=4 -> интерфейс отправит 2 (marital_status='single')
    X_all = df[FEATURE_COLUMNS]
    w = X_all[X_all["personal_status_sex"] == 4]
    w2 = w.copy()
    w2["personal_status_sex"] = 2
    r1, r2 = score(model, calibrator, meta, w), score(model, calibrator, meta, w2)
    skew = {"n_code4": int(len(w)),
            "mean_pd_code4": float(r1["pd"].mean()), "mean_pd_as_code2": float(r2["pd"].mean()),
            "mean_delta_pp": float((r2["pd"] - r1["pd"]).mean() * 100),
            "max_abs_delta_pp": float((r2["pd"] - r1["pd"]).abs().max() * 100),
            "recommendation_changed": int((r1["recommendation"] != r2["recommendation"]).sum()),
            "fact_default_rate_code4": float(df.loc[w.index, "default"].mean()),
            "fact_default_rate_code2": float(df.loc[df["personal_status_sex"] == 2, "default"].mean())}
    # Направление по foreign_worker (связь с анализом чувствительности)
    f2 = X_all.copy()
    f2["foreign_worker"] = 3 - f2["foreign_worker"]
    p0 = score(model, calibrator, meta, X_all)["pd"]
    p1 = calibrate(calibrator, model.predict_proba(f2)[:, 1])
    skew["foreign_flip_mean_delta_pp_for_foreigners"] = float(
        (p1[X_all["foreign_worker"] == 1] - p0[X_all["foreign_worker"] == 1]).mean() * 100)
    skew["foreign_flip_mean_delta_pp_for_locals"] = float(
        (p1[X_all["foreign_worker"] == 2] - p0[X_all["foreign_worker"] == 2]).mean() * 100)
    meta_info["interface_and_flip"] = skew

    # Правило для молодых: что оно даёт и чего стоит (OOF)
    young = full[full["g_age"] == "<=25"]
    meta_info["young_rule"] = {
        "n_young": int(len(young)),
        "triggered": int(young["rule_young"].sum()),
        "triggered_good": int((young["rule_young"] & (young["default"] == 0)).sum()),
        "triggered_bad": int((young["rule_young"] & (young["default"] == 1)).sum()),
        "per_1000_applications": float(full["rule_young"].mean() * 1000),
    }
    (OUT / "run_metadata.json").write_text(json.dumps(meta_info, ensure_ascii=False, indent=2),
                                           encoding="utf-8")

    plot_slide(t_oof, FIG / "group_quality_final.png")
    plot_calibration(t_oof, FIG / "calibration_by_group.png")
    print(json.dumps(meta_info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
