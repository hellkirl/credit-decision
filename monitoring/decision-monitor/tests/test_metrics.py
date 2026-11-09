"""Тесты расчёта метрик. Запуск из папки decision-monitor: python -m pytest tests -q"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import parse_window  # noqa: E402
from app.encoding import _go_round, codes_to_applicant, journal_to_codes, row_to_codes  # noqa: E402
from app.metrics import actual_shares, compute_snapshot, psi  # noqa: E402

REFERENCE = json.loads((ROOT / "reference" / "reference.json").read_text(encoding="utf-8"))
DEMO = pd.read_csv(ROOT / "reference" / "demo_applications.csv")
RUB_PER_DM = 49.1


def test_psi_zero_when_same_distribution():
    assert psi([0.25] * 4, [0.25] * 4) == pytest.approx(0.0)


def test_psi_grows_with_shift():
    small = psi([0.5, 0.5], [0.55, 0.45])
    big = psi([0.5, 0.5], [0.9, 0.1])
    assert 0 < small < 0.1 < 0.25 < big


def test_unseen_category_goes_to_extra_bucket():
    profile = {"type": "categorical", "categories": [1, 2], "expected": [0.5, 0.5]}
    expected, actual = actual_shares(pd.Series([1, 2, 7, 7]), profile)
    assert list(expected) == [0.5, 0.5, 0.0]
    assert list(actual) == [0.25, 0.25, 0.5]


def test_go_round_half_away_from_zero():
    assert _go_round(2.5) == 3 and _go_round(3.5) == 4 and _go_round(2.4) == 2


def test_parse_window():
    assert parse_window("30d") == 30 * 86400 and parse_window("15m") == 900
    with pytest.raises(ValueError):
        parse_window("month")


def _journal_from_demo(demo: pd.DataFrame) -> pd.DataFrame:
    """Демо-заявки -> строки журнала applications, как их сохранит backend."""
    rows = []
    for i, c in enumerate(demo.to_dict("records")):
        body = codes_to_applicant(c, RUB_PER_DM, borrower=f"t{i}")
        body.pop("draft")
        rows.append({**body, "id": i, "default_probability": 0.3, "recommendation": "review",
                     "triggered_rules": [], "defaulted": float(c["credit_risk"] == 0)})
    return pd.DataFrame(rows)


def test_round_trip_keeps_expressible_codes():
    """Коды -> тело запроса -> коды: совпадают везде, где интерфейс может это выразить."""
    journal = _journal_from_demo(DEMO)
    back = journal_to_codes(journal, RUB_PER_DM)
    for col in ["duration", "amount", "age", "status", "credit_history", "savings",
                "installment_rate", "present_residence", "property", "number_credits",
                "housing", "people_liable", "telephone", "foreign_worker"]:
        assert (back[col] == DEMO[col]).all(), col


def test_snapshot_false_reject_gap():
    """Две группы по 40 хороших клиентов: молодым отказывают в 50%, остальным в 10%."""
    n = 40
    journal = pd.DataFrame({
        "age": [22] * n + [40] * n,
        "marital_status": ["single"] * (2 * n),
        "foreign_worker": [False] * (2 * n),
        "default_probability": [0.4] * n + [0.2] * n,
        "recommendation": ["reject"] * 20 + ["review"] * 20 + ["reject"] * 4 + ["review"] * 36,
        "triggered_rules": [[] for _ in range(2 * n)],
        "defaulted": [0.0] * (2 * n),
    })
    codes = pd.DataFrame({f: [1] * (2 * n) for f in REFERENCE["features"]})
    snap = compute_snapshot(journal, codes, REFERENCE)
    assert snap.get("credit_false_reject_rate", group="all") == pytest.approx(0.3)
    assert snap.get("credit_false_reject_gap_pp", group="<=25") == pytest.approx(20.0)
    assert snap.get("credit_false_reject_gap_pp", group="36-50") == pytest.approx(-20.0)
    # группы < 30 заявок не получают долей, только счётчик
    assert snap.get("credit_monitor_applications", group="26-35") == 0
    assert snap.get("credit_zone_share", group="26-35", zone="reject") is None


def test_snapshot_without_outcomes_has_no_layer2():
    journal = _journal_from_demo(DEMO)
    journal["defaulted"] = np.nan
    snap = compute_snapshot(journal, journal_to_codes(journal, RUB_PER_DM), REFERENCE)
    assert snap.get("credit_outcomes_labeled", group="all") == 0
    assert "credit_calibration_default_rate" not in snap.samples
    assert snap.get("credit_feature_psi", feature="age") is not None
    assert snap.get("credit_rule_triggered_share", rule="YOUNG_APPLICANT_REVIEW") == 0


def test_unscored_applications_counted_but_excluded_from_pd():
    journal = _journal_from_demo(DEMO.head(60))
    journal.loc[:9, "default_probability"] = np.nan   # 10 неизвестных заявок
    journal.loc[:9, "triggered_rules"] = pd.Series([["NUMERIC_OUT_OF_RANGE: amount"]] * 10)
    snap = compute_snapshot(journal, journal_to_codes(journal, RUB_PER_DM), REFERENCE)
    assert snap.get("credit_monitor_applications", group="all") == 60
    assert snap.get("credit_unscored_share", group="all") == pytest.approx(10 / 60)
    assert snap.get("credit_pd_mean", group="all") == pytest.approx(0.3)
    assert snap.get("credit_rule_triggered_share", rule="NUMERIC_OUT_OF_RANGE") == pytest.approx(10 / 60)
    assert snap.get("credit_feature_psi", feature="pd") is not None   # 50 оценённых — хватает
