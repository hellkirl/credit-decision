"""Чтение журнала решений из Postgres (таблица applications, её ведёт backend).

Мониторинг только читает applications. Исходы (вернул ли клиент кредит)
лежат в отдельной таблице loan_outcomes (sql/001_loan_outcomes.sql): в жизни их
заполняет учётная система через месяцы после выдачи, в демо — simulate_traffic.py.
"""
from __future__ import annotations

import pandas as pd
import psycopg

COLUMNS = [
    "id", "created_at", "age", "marital_status", "foreign_worker", "housing", "phone",
    "residence_years", "property", "job", "employment_months", "amount", "term_months",
    "purpose", "installment_rate", "checking_status", "other_installment_plans", "savings",
    "other_debtors", "credit_history", "existing_credits", "dependents",
    "default_probability", "risk", "recommendation", "triggered_rules", "decision",
]

# Все отправленные на оценку заявки (без черновиков) за последние N секунд.
# Заявки без PD (неизвестные: вне диапазона обучения) тоже берём — их доля сама по себе сигнал.
BASE_QUERY = """
SELECT {cols}{outcome_col}
FROM applications a
{outcome_join}
WHERE a.status <> 'draft'
  AND a.created_at >= now() - make_interval(secs => %s)
"""


def load_journal(database_url: str, window_seconds: int) -> pd.DataFrame:
    with psycopg.connect(database_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.loan_outcomes') IS NOT NULL")
            has_outcomes = cur.fetchone()[0]
            query = BASE_QUERY.format(
                cols=", ".join(f"a.{c}" for c in COLUMNS),
                outcome_col=", o.defaulted::int AS defaulted" if has_outcomes else ", NULL::int AS defaulted",
                outcome_join="LEFT JOIN loan_outcomes o ON o.application_id = a.id" if has_outcomes else "",
            )
            cur.execute(query, (float(window_seconds),))
            rows = cur.fetchall()
    return pd.DataFrame(rows, columns=COLUMNS + ["defaulted"])
