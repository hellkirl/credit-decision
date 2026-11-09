"""Перевод строки журнала заявок в коды признаков модели.

В таблице applications поля хранятся «по-человечески» (marital_status='single',
amount в рублях и т. д.), а модель и эталон (reference.json) живут в кодах
South German Credit. Чтобы сравнивать распределения, переводим журнал в те же
коды ровно так, как это делает backend перед вызовом ML-сервиса.

Это копия backend/internal/adapters/out/ml/features.go (функция toFeatures).
Если там поменяют маппинг — поменять и здесь, иначе дрейф будет ложным.
"""
from __future__ import annotations

import math

import pandas as pd

CHECKING = {"none": 1, "lt_0": 2, "0_200": 3, "ge_200": 4}
CREDIT_HISTORY = {"delayed": 0, "critical": 1, "no_credits": 2, "existing_paid": 3, "all_paid": 4}
PURPOSE = {
    "other": 0, "new_car": 1, "used_car": 2, "furniture": 3, "electronics": 4,
    "repairs": 6, "education": 7, "retraining": 9, "business": 10,
}
SAVINGS = {"unknown": 1, "lt_100": 2, "100_500": 3, "500_1000": 4, "ge_1000": 5}
PERSONAL_STATUS = {"divorced": 1, "single": 2, "married": 3, "widowed": 3}
PROPERTY = {"none": 1, "car": 2, "savings_insurance": 3, "real_estate": 4}
HOUSING = {"free": 1, "rent": 2, "own": 3}
JOB = {"unemployed": 1, "unskilled": 2, "skilled": 3, "management": 4}


def _employment_code(job: str, months: int) -> int:
    if job == "unemployed":
        return 1
    if months < 12:
        return 2
    if months < 48:
        return 3
    if months < 84:
        return 4
    return 5


def _installment_rate_code(pct: float) -> int:
    if pct >= 35:
        return 1
    if pct >= 25:
        return 2
    if pct >= 20:
        return 3
    return 4


def _residence_code(years: int) -> int:
    if years < 1:
        return 1
    if years < 4:
        return 2
    if years < 7:
        return 3
    return 4


def _credits_code(n: int) -> int:
    if n <= 1:
        return 1
    if n <= 3:
        return 2
    if n <= 5:
        return 3
    return 4


def _go_round(x: float) -> int:
    """math.Round из Go: половина округляется от нуля (у Python round — к чётному)."""
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


def row_to_codes(row: dict, rub_per_dm: float) -> dict:
    """Одна строка журнала (dict колонок applications) → 20 признаков модели."""
    return {
        "duration": int(row["term_months"]),
        "amount": max(1, _go_round(float(row["amount"]) / rub_per_dm)),
        "age": int(row["age"]),
        "status": CHECKING.get(row["checking_status"], 0),
        "credit_history": CREDIT_HISTORY.get(row["credit_history"], 0),
        "savings": SAVINGS.get(row["savings"], 0),
        "employment_duration": _employment_code(row["job"], int(row["employment_months"])),
        "installment_rate": _installment_rate_code(float(row["installment_rate"])),
        "present_residence": _residence_code(int(row["residence_years"])),
        "property": PROPERTY.get(row["property"], 0),
        "number_credits": _credits_code(int(row["existing_credits"])),
        "job": JOB.get(row["job"], 0),
        "purpose": PURPOSE.get(row["purpose"], 0),
        "personal_status_sex": PERSONAL_STATUS.get(row["marital_status"], 0),
        "other_debtors": 2 if row["other_debtors"] else 1,
        "other_installment_plans": 1 if row["other_installment_plans"] else 3,
        "housing": HOUSING.get(row["housing"], 0),
        "people_liable": 1 if int(row["dependents"]) >= 3 else 2,
        "telephone": 2 if row["phone"] else 1,
        "foreign_worker": 1 if row["foreign_worker"] else 2,
    }


def journal_to_codes(journal: pd.DataFrame, rub_per_dm: float) -> pd.DataFrame:
    """Весь журнал → таблица кодов (индекс тот же, что у журнала)."""
    records = [row_to_codes(r, rub_per_dm) for r in journal.to_dict("records")]
    return pd.DataFrame(records, index=journal.index)


# ---- Обратное направление: коды датасета → тело запроса POST /applications ----
# Нужно только для демо-прогона (scripts/simulate_traffic.py). Не всё из датасета
# можно ввести через интерфейс: см. комментарии «теряется» — это и есть
# расхождение между обучающими данными и тем, что реально приходит в модель.
def _inverse(mapping: dict[str, int]) -> dict[int, str]:
    out: dict[int, str] = {}
    for name, code in mapping.items():
        out.setdefault(code, name)
    return out


def codes_to_applicant(c: dict, rub_per_dm: float, borrower: str) -> dict:
    return {
        "draft": False,
        "borrower": borrower,
        "checking_status": _inverse(CHECKING)[c["status"]],
        "term_months": int(c["duration"]),
        "credit_history": _inverse(CREDIT_HISTORY)[c["credit_history"]],
        # 5 (бытовая техника) и 8 (отпуск) в интерфейсе нет → «другое»: теряется
        "purpose": _inverse(PURPOSE).get(c["purpose"], "other"),
        "amount": int(round(c["amount"] * rub_per_dm)),
        "savings": _inverse(SAVINGS)[c["savings"]],
        # job=1 в интерфейсе = «безработный», и стаж тогда всегда код 1: теряется
        "job": _inverse(JOB)[c["job"]],
        "employment_months": {1: 0, 2: 6, 3: 24, 4: 60, 5: 120}[c["employment_duration"]],
        "installment_rate": {1: 40.0, 2: 30.0, 3: 22.0, 4: 15.0}[c["installment_rate"]],
        # 4 (женщина, одна) в интерфейсе нет (пол не собирается) → single = код 2: теряется
        "marital_status": {1: "divorced", 2: "single", 3: "married", 4: "single"}[c["personal_status_sex"]],
        # 3 (поручитель) неотличим от 2 (созаёмщик): теряется
        "other_debtors": c["other_debtors"] != 1,
        "residence_years": {1: 0, 2: 2, 3: 5, 4: 8}[c["present_residence"]],
        "property": _inverse(PROPERTY)[c["property"]],
        "age": int(c["age"]),
        # 2 (магазины) неотличим от 1 (банк): теряется
        "other_installment_plans": c["other_installment_plans"] != 3,
        "housing": _inverse(HOUSING)[c["housing"]],
        "existing_credits": {1: 1, 2: 2, 3: 4, 4: 6}[c["number_credits"]],
        "dependents": 3 if c["people_liable"] == 1 else 1,
        "phone": c["telephone"] == 2,
        "foreign_worker": c["foreign_worker"] == 1,
    }
