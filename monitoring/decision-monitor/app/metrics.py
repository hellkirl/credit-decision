"""Расчёт метрик мониторинга решения. Чистые функции: на входе таблицы, на выходе числа.

Здесь нет ни базы, ни Prometheus — поэтому всё это легко проверить тестами
(tests/test_metrics.py) и при желании прогнать в Colab на CSV.

Два слоя метрик:
  1. Без исходов — видны сразу после решения: сколько заявок, доли зон,
     средний PD, дрейф признаков (PSI), срабатывания правил.
  2. С исходами — когда стало известно, вернул ли клиент кредит: калибровка
     (средний PD против фактической доли дефолтов) и ложные отказы по группам.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

PSI_EPS = 1e-4  # чтобы не делить на ноль и не брать log(0) в пустых корзинах

AGE_BINS = [-np.inf, 25, 35, 50, np.inf]
AGE_LABELS = ["<=25", "26-35", "36-50", ">50"]  # границы зафиксированы на Этапе 2

KNOWN_RULES = ["YOUNG_APPLICANT_REVIEW", "NUMERIC_OUT_OF_RANGE", "UNSEEN_CATEGORY"]
ZONES = ["approve", "review", "reject"]


# Снимок: имя метрики -> список (метки, значение). Экспортёр отдаёт его в Prometheus.
@dataclass
class Snapshot:
    samples: dict[str, list[tuple[dict[str, str], float]]] = field(default_factory=dict)

    def add(self, metric: str, labels: dict[str, str], value: float) -> None:
        self.samples.setdefault(metric, []).append((labels, float(value)))

    def get(self, metric: str, **labels: str) -> float | None:
        """Удобно для тестов: значение метрики с заданными метками."""
        for lbl, value in self.samples.get(metric, []):
            if all(lbl.get(k) == v for k, v in labels.items()):
                return value
        return None


# ---------------------------------------------------------------- PSI -------
def psi(expected: np.ndarray, actual: np.ndarray) -> float:
    """Population Stability Index: насколько распределение сдвинулось от эталона.

    PSI = Σ (доля_сейчас − доля_эталон) · ln(доля_сейчас / доля_эталон)
    Ориентиры: < 0.1 — стабильно, 0.1–0.25 — заметный сдвиг, > 0.25 — сильный.
    """
    e = np.clip(np.asarray(expected, dtype=float), PSI_EPS, None)
    a = np.clip(np.asarray(actual, dtype=float), PSI_EPS, None)
    return float(np.sum((a - e) * np.log(a / e)))


def actual_shares(values: pd.Series, profile: dict) -> tuple[np.ndarray, np.ndarray]:
    """Раскладывает текущие значения по корзинам эталона. Возвращает (эталон, сейчас)."""
    values = values.dropna()
    expected = np.asarray(profile["expected"], dtype=float)
    if profile["type"] == "numeric":
        idx = np.digitize(values.to_numpy(dtype=float), profile["edges"], right=True)
        counts = np.bincount(idx, minlength=len(expected))
        return expected, counts / max(len(values), 1)
    # Категориальный: доля каждой известной категории + корзина «не встречалось в обучении»
    cats = profile["categories"]
    counts = np.array([(values == c).sum() for c in cats], dtype=float)
    unseen = len(values) - counts.sum()
    return np.append(expected, 0.0), np.append(counts, unseen) / max(len(values), 1)


# ------------------------------------------------------------- группы -------
def groups(journal: pd.DataFrame) -> list[tuple[str, str, pd.Series]]:
    """Все разрезы для проверки различий: (тип группы, группа, маска строк)."""
    out = [("all", "all", pd.Series(True, index=journal.index))]
    age_band = pd.cut(journal["age"], bins=AGE_BINS, labels=AGE_LABELS)
    for label in AGE_LABELS:
        out.append(("age", label, age_band == label))
    for status in sorted(journal["marital_status"].dropna().unique()):
        out.append(("marital_status", str(status), journal["marital_status"] == status))
    fw = journal["foreign_worker"].astype("boolean")
    out.append(("foreign_worker", "yes", fw == True))   # noqa: E712 — маска pandas
    out.append(("foreign_worker", "no", fw == False))   # noqa: E712
    return out


def _rule_codes(rules) -> set[str]:
    """['YOUNG_APPLICANT_REVIEW: age'] -> {'YOUNG_APPLICANT_REVIEW'}"""
    if rules is None or (isinstance(rules, float) and np.isnan(rules)):
        return set()
    return {str(r).split(":", 1)[0].strip() for r in rules if str(r).strip()}


# ------------------------------------------------------- основной расчёт ----
def compute_snapshot(
    journal: pd.DataFrame,
    codes: pd.DataFrame,
    reference: dict,
    min_group_size: int = 30,
    min_psi_sample: int = 50,
) -> Snapshot:
    """journal — оценённые заявки за окно (+ колонка defaulted: 1/0/NaN),
    codes — те же заявки в кодах модели (encoding.journal_to_codes)."""
    snap = Snapshot()
    n_total = len(journal)
    pd_col = journal["default_probability"].astype(float)  # NaN = заявка без PD (неизвестная)
    scored = pd_col.notna()
    rec = journal["recommendation"]
    defaulted = journal["defaulted"].astype(float) if "defaulted" in journal else pd.Series(np.nan, index=journal.index)
    labeled = defaulted.notna()

    # ---- Слой 1: без исходов ------------------------------------------
    for gtype, gname, mask in groups(journal):
        g = {"group_type": gtype, "group": gname}
        n = int(mask.sum())
        snap.add("credit_monitor_applications", g, n)
        # Мало заявок — выводов не делаем, ряд не отдаём (правило Этапа 2: n < 30)
        if n == 0 or (gtype != "all" and n < min_group_size):
            continue
        for zone in ZONES:
            snap.add("credit_zone_share", {**g, "zone": zone}, (rec[mask] == zone).mean())
        snap.add("credit_unscored_share", g, (~scored[mask]).mean())
        if scored[mask].any():
            snap.add("credit_pd_mean", g, pd_col[mask].mean())

    if int(scored.sum()) >= min_psi_sample:
        snap.add("credit_feature_psi", {"feature": "pd"}, psi(*actual_shares(pd_col, reference["pd"])))
        for feature, profile in reference["features"].items():
            snap.add("credit_feature_psi", {"feature": feature}, psi(*actual_shares(codes[feature], profile)))

    rule_sets = journal["triggered_rules"].map(_rule_codes) if n_total else pd.Series(dtype=object)
    seen = set().union(*rule_sets) if n_total else set()
    for rule in sorted(set(KNOWN_RULES) | seen):
        share = rule_sets.map(lambda s, r=rule: r in s).mean() if n_total else 0.0
        snap.add("credit_rule_triggered_share", {"rule": rule}, share)

    # ---- Слой 2: с исходами --------------------------------------------
    rates: dict[tuple[str, str], float] = {}
    for gtype, gname, mask in groups(journal):
        g = {"group_type": gtype, "group": gname}
        m = mask & labeled
        n = int(m.sum())
        snap.add("credit_outcomes_labeled", g, n)
        if n == 0 or (gtype != "all" and n < min_group_size):
            continue
        ms = m & scored  # калибровку сравниваем только там, где PD был
        if ms.any():
            snap.add("credit_calibration_pd_mean", g, pd_col[ms].mean())
            snap.add("credit_calibration_default_rate", g, defaulted[ms].mean())
        good = m & (defaulted == 0)  # клиент на деле вернул кредит
        if good.sum() > 0:
            rate = (rec[good] == "reject").mean()  # …а система рекомендовала отказ
            snap.add("credit_false_reject_rate", g, rate)
            rates[(gtype, gname)] = rate

    overall = rates.get(("all", "all"))
    if overall is not None:
        for (gtype, gname), rate in rates.items():
            if gtype != "all":
                snap.add("credit_false_reject_gap_pp",
                         {"group_type": gtype, "group": gname}, (rate - overall) * 100)
    return snap
