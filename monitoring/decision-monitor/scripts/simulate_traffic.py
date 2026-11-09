#!/usr/bin/env python3
"""Демо-прогон: отправляет заявки через backend и записывает их исходы.

Заявки идут по настоящему пути (backend -> ML -> правила -> журнал в Postgres),
поэтому мониторинг видит их ровно так, как увидит боевые. Исход (вернул ли
клиент кредит) берётся из тестовой выборки и пишется в loan_outcomes.

Режимы:
  normal       — 200 тестовых заявок как есть: «обычный день».
  young_shift  — 200 заявок, перекошенных в молодых (<=25 в 6 раз чаще):
                 например, банк запустил рекламу для студентов. Должны вырасти
                 PSI по age и pd, доля молодых и средний PD.

Запуск внутри контейнера мониторинга (там есть сеть до backend и база):
  docker compose -f monitoring/docker-compose.yml exec decision-monitor \
      python scripts/simulate_traffic.py --mode normal --login ivan.ivanov --password ...
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.encoding import codes_to_applicant  # noqa: E402

DEMO_CSV = ROOT / "reference" / "demo_applications.csv"
OUTCOMES_SQL = ROOT / "sql" / "001_loan_outcomes.sql"


def http_json(url: str, body: dict, token: str | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def pick_applications(mode: str, n: int, seed: int) -> pd.DataFrame:
    demo = pd.read_csv(DEMO_CSV)
    if mode == "normal":
        return demo.head(n)
    rng = np.random.default_rng(seed)
    weights = np.where(demo["age"] <= 25, 6.0, 1.0)
    idx = rng.choice(len(demo), size=n, replace=True, p=weights / weights.sum())
    return demo.iloc[idx].reset_index(drop=True)


def main() -> None:
    p = argparse.ArgumentParser(description="Демо-поток заявок для мониторинга")
    p.add_argument("--mode", choices=["normal", "young_shift"], default="normal")
    p.add_argument("-n", type=int, default=200, help="сколько заявок отправить")
    p.add_argument("--backend", default=os.environ.get("BACKEND_URL", "http://backend:5000"))
    p.add_argument("--login", default=os.environ.get("DEMO_LOGIN"))
    p.add_argument("--password", default=os.environ.get("DEMO_PASSWORD"))
    p.add_argument("--rub-per-dm", type=float, default=float(os.environ.get("RUB_PER_DM", "49.1")))
    p.add_argument("--delay", type=float, default=0.05, help="пауза между заявками, с")
    p.add_argument("--skip-outcomes", action="store_true",
                   help="не записывать исходы (показать, что слой 2 пуст, пока меток нет)")
    p.add_argument("--seed", type=int, default=7)
    args = p.parse_args()
    if not args.login or not args.password:
        p.error("нужны --login и --password (SEED_USER_LOGIN / SEED_USER_PASSWORD из .env)")

    status, resp = http_json(f"{args.backend}/auth/login", {"login": args.login, "password": args.password})
    if status != 200:
        sys.exit(f"login failed: {status} {resp}")
    token = resp["access_token"]

    apps = pick_applications(args.mode, args.n, args.seed)
    outcomes: list[tuple[int, bool]] = []
    errors = 0
    for i, row in enumerate(apps.to_dict("records"), start=1):
        body = codes_to_applicant(row, args.rub_per_dm, borrower=f"Демо {args.mode} {i:03d}")
        status, resp = http_json(f"{args.backend}/applications", body, token)
        if status == 201:
            outcomes.append((int(resp["id"]), row["credit_risk"] == 0))  # target 1 = good
        else:
            errors += 1
            print(f"  заявка {i}: {status} {resp}", file=sys.stderr)
        time.sleep(args.delay)
    print(f"отправлено {len(apps)}, создано {len(outcomes)}, ошибок {errors}")

    if args.skip_outcomes or not outcomes:
        return
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute(OUTCOMES_SQL.read_text(encoding="utf-8"))
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO loan_outcomes (application_id, defaulted) VALUES (%s, %s) "
                "ON CONFLICT (application_id) DO UPDATE SET defaulted = EXCLUDED.defaulted",
                outcomes,
            )
    print(f"исходы записаны: {len(outcomes)}, дефолтов {sum(d for _, d in outcomes)}")


if __name__ == "__main__":
    main()
