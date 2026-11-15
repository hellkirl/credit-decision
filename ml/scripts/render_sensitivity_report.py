#!/usr/bin/env python3
"""Render saved sensitivity results with matplotlib; never call scoring APIs.

Usage: python ml/scripts/render_sensitivity_report.py --run-dir PATH
Only figures/, REPORT.md, PRESENTATION_NOTES.md and derived tables are written.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

METRICS = {
    "mean_abs_delta_pd": (
        "Среднее абсолютное изменение PD по признакам",
        "Среднее |ΔPD|",
        "mean_abs_delta_pd.png",
        False,
    ),
    "recommendation_change_share": (
        "Чувствительность итоговой рекомендации к признакам",
        "Доля вариантов со сменой рекомендации",
        "recommendation_change_share.png",
        True,
    ),
    "pd_zone_change_share": (
        "Чувствительность зоны риска к признакам",
        "Доля вариантов со сменой pd_zone",
        "pd_zone_change_share.png",
        True,
    ),
}
CASE_FIELDS = [
    "feature",
    "base_value",
    "variant_value",
    "base_pd",
    "variant_pd",
    "delta_pd",
    "base_pd_zone",
    "variant_pd_zone",
    "base_recommendation",
    "variant_recommendation",
    "variant_reasons",
]
TRANSITIONS = ["approve->review", "review->reject", "reject->review", "review->approve"]


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def number(value):
    return None if value in (None, "") else float(value)


def display(value):
    if value is None or value == "":
        return "—"
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def table(rows, fields):
    def cell(value):
        return display(value).replace("|", "\\|").replace("\n", " ")

    return "\n".join(
        [
            "| " + " | ".join(fields) + " |",
            "| " + " | ".join("---" for _ in fields) + " |",
            *(
                "| " + " | ".join(cell(row.get(field)) for field in fields) + " |"
                for row in rows
            ),
        ]
    )


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(row.get(key), ensure_ascii=False)
                    if isinstance(row.get(key), (dict, list))
                    else row.get(key)
                    for key in fields
                }
            )


def validate(summary, rows, baselines, cases, metadata):
    """Refuse to present inconsistent saved files as a successful experiment."""
    if (
        len(rows) != metadata["variant_count"]
        or len(baselines) != metadata["baseline_count"]
    ):
        raise ValueError("CSV counts differ from run_metadata.json")
    if len({r["variant_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate variant_id")
    for field, metadata_key in [
        ("pd_zone_changed", "pd_zone_changes"),
        ("recommendation_changed", "recommendation_changes"),
    ]:
        if sum(r[field] == "True" for r in rows) != metadata[metadata_key]:
            raise ValueError(f"Inconsistent {field}")
    for entry in summary:
        subset = [r for r in rows if r["feature"] == entry["feature"]]
        if len(subset) != int(entry["variant_count"]):
            raise ValueError(f"Inconsistent variant count: {entry['feature']}")
        for metric in METRICS:
            value = number(entry[metric])
            if value is None or not math.isfinite(value):
                raise ValueError(f"Missing/non-finite {metric} for {entry['feature']}")
    by_id = {r["variant_id"]: r for r in rows}
    for transition in TRANSITIONS:
        group = cases.get("recommendation_transitions", {}).get(transition)
        if group is None:
            continue
        source, target = transition.split("->")
        actual = sum(
            r["base_recommendation"] == source and r["variant_recommendation"] == target
            for r in rows
        )
        if actual != group["count"]:
            raise ValueError(f"Inconsistent transition count: {transition}")
    groups = list(cases.get("recommendation_transitions", {}).values())
    groups.append(cases.get("business_rule_overrides", {}))
    for group in groups:
        for case in group.get("cases", []):
            saved = by_id[case["variant_id"]]
            for field in CASE_FIELDS:
                value = saved[field]
                if field in ("base_pd", "variant_pd", "delta_pd"):
                    equal = number(value) == case[field]
                elif field == "variant_reasons":
                    equal = json.loads(value) == case[field]
                else:
                    equal = str(value) == str(case[field])
                if not equal:
                    raise ValueError(
                        f"Case differs from CSV: {case['variant_id']}, {field}"
                    )


def plot_ranking(summary, metric, destination):
    title, xlabel, filename, percent = METRICS[metric]
    ranked = sorted(summary, key=lambda row: float(row[metric]), reverse=True)
    values = [float(row[metric]) for row in ranked]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 13})
    fig, ax = plt.subplots(figsize=(13, 10), layout="constrained")
    bars = ax.barh([row["feature"] for row in ranked], values, color="#31688e")
    ax.invert_yaxis()
    ax.set_title(title, fontsize=17, pad=18)
    ax.set_xlabel(xlabel, fontsize=14, labelpad=10)
    ax.set_xlim(0, max(values) * 1.2 if max(values) else 1)
    if percent:
        ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.bar_label(
        bars,
        labels=[f"{v:.1%}" if percent else f"{v:.4f}" for v in values],
        padding=6,
        fontsize=12,
    )
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    fig.savefig(destination / filename, dpi=200, facecolor="white")
    plt.close(fig)


def render(run_dir):
    summary = read_csv(run_dir / "sensitivity_summary.csv")
    rows = read_csv(run_dir / "sensitivity_results.csv")
    baselines = read_csv(run_dir / "baselines.csv")
    cases = json.loads((run_dir / "transition_cases.json").read_text(encoding="utf-8"))
    metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    validate(summary, rows, baselines, cases, metadata)
    figures = run_dir / "figures"
    figures.mkdir(exist_ok=True)
    for metric in METRICS:
        plot_ranking(summary, metric, figures)

    rankings, ranking_text = [], []
    for metric, (title, _, _, percent) in METRICS.items():
        top = sorted(summary, key=lambda r: float(r[metric]), reverse=True)[:5]
        ranking_text.append(
            f"### {title}\n\n"
            + table(
                [
                    {
                        "Место": index,
                        "Признак": row["feature"],
                        "Значение": f"{float(row[metric]):.2%}"
                        if percent
                        else f"{float(row[metric]):.4f}",
                    }
                    for index, row in enumerate(top, 1)
                ],
                ["Место", "Признак", "Значение"],
            )
        )
        rankings.extend(
            {
                "metric": metric,
                "rank": index,
                "feature": row["feature"],
                "value": row[metric],
            }
            for index, row in enumerate(top, 1)
        )
    write_csv(
        run_dir / "top5_rankings.csv", rankings, ["metric", "rank", "feature", "value"]
    )

    selected, case_text, missing = [], [], []
    for transition in TRANSITIONS:
        group = cases.get("recommendation_transitions", {}).get(transition, {})
        available = group.get("cases", [])
        if not available:
            missing.append(transition)
            case_text.append(
                f"### {transition}\n\nПример этого перехода не найден в transition_cases.json."
            )
            continue
        # Prefer the explicitly requested observed status 4 -> 1 case.
        case = next(
            (
                c
                for c in available
                if c["feature"] == "status"
                and c["base_value"] == 4
                and c["variant_value"] == 1
            ),
            available[0],
        )
        selected.append(
            {
                "case_type": transition,
                "base_id": case["base_id"],
                "variant_id": case["variant_id"],
                **{f: case[f] for f in CASE_FIELDS},
            }
        )
        case_text.append(
            f"### {transition}\n\nНайдено вариантов: {group['count']}. "
            f"Пример `{case['variant_id']}`:\n\n" + table([case], CASE_FIELDS)
        )
    overrides = cases.get("business_rule_overrides", {}).get("cases", [])
    young = next(
        (
            c
            for c in overrides
            if c["variant_pd_zone"] == "reject"
            and c["variant_recommendation"] == "review"
            and any(
                r.get("code") == "YOUNG_APPLICANT_REVIEW" for r in c["variant_reasons"]
            )
        ),
        None,
    )
    if young:
        selected.append(
            {
                "case_type": "business_rule",
                "base_id": young["base_id"],
                "variant_id": young["variant_id"],
                **{f: young[f] for f in CASE_FIELDS},
            }
        )
        rule_text = (
            f"Пример `{young['variant_id']}`, возраст "
            f"{young['variant_features']['age']} лет:\n\n"
            + table([young], CASE_FIELDS)
            + "\n\nПри `pd_zone=reject` API возвращает `recommendation=review` "
            "и причину `YOUNG_APPLICANT_REVIEW`. Итоговая автоматическая рекомендация "
            "зависит не только от PD, но и от правил поверх модели."
        )
    else:
        missing.append("YOUNG_APPLICANT_REVIEW override")
        rule_text = "Кейс reject → review из-за YOUNG_APPLICANT_REVIEW не найден в сохранённых примерах."
    write_csv(
        run_dir / "selected_transition_cases.csv",
        selected,
        ["case_type", "base_id", "variant_id", *CASE_FIELDS],
    )

    total = len(rows)
    zone_changes = metadata["pd_zone_changes"]
    rec_changes = metadata["recommendation_changes"]
    errors = sum(r["scoring_status"] == "http_error" for r in rows)
    response_errors = sum(r["scoring_status"] == "response_error" for r in rows)
    screening_errors = sum(
        r["scoring_status"] in ("http_error", "response_error")
        for r in metadata["excluded_test_applications"]
    )
    top_pd = sorted(summary, key=lambda r: float(r["mean_abs_delta_pd"]), reverse=True)[
        :5
    ]
    top_description = ", ".join(
        f"`{r['feature']}` ({float(r['mean_abs_delta_pd']):.4f})" for r in top_pd
    )
    by_feature = {r["feature"]: r for r in summary}
    age = by_feature["age"]
    excluded = [
        r
        for r in metadata["excluded_test_applications"]
        if r["scoring_status"] == "null_pd"
    ]
    exclusion_text = (
        f"Из выбора baseline исключено строк тестовой выборки с `pd=null`: {len(excluded)}. "
        + "; ".join(
            f"`{r['base_id']}`: " + json.dumps(r["reasons"], ensure_ascii=False)
            for r in excluded
        )
        + "."
    )
    conclusions = [
        f"На {len(baselines)} базовых заявках проверено {total:,} уникальных вариантов с изменением одного признака.",
        f"Наибольшая средняя чувствительность PD наблюдается для `{top_pd[0]['feature']}`: {float(top_pd[0]['mean_abs_delta_pd']):.4f}.",
        f"Количество изменений зоны по PD — {zone_changes}, итоговой рекомендации — {rec_changes}.",
        "Рейтинги чувствительности PD, зоны и рекомендации различаются; общий score не рассчитывался.",
        "Бизнес-правило для молодых заявителей может сохранить review при зоне reject."
        if young
        else "Пример бизнес-правила не найден в сохранённых кейсах.",
        "Выводы описывают текущую модель и выбранную стратегию изменения входов, а не причинное влияние признаков.",
    ]
    report = f"""# Анализ чувствительности кредитного решения к признакам

## Цель

Проверить влияние изменения одного ML-признака при фиксированных остальных на калиброванный PD,
пороговую зону `pd_zone` и автоматическую рекомендацию `recommendation`.

## Методика

Использованы {len(baselines)} базовых заявок и {total:,} уникальных вариантов. Базы взяты из тестовой
части South German Credit ({metadata["test_count"]} строк; seed разбиения {metadata["split_random_state"]}).
Выбор включает разные зоны, близость к порогам, возрастам 25/26 и случайные строки с seed {metadata["config"]["seed"]}.
Распределение баз по pd_zone: {json.dumps(metadata["baseline_zone_counts"], ensure_ascii=False)}.

В каждом варианте изменён ровно один признак. Скоринг выполнен через ML API `{metadata["endpoint"]}`.
Для числовых признаков использованы локальные изменения
{", ".join(f"{v:+.0%}" for v in metadata["config"]["numeric_relative_changes"])}, округление до int
и ограничение обучающим диапазоном; для age дополнительно — {metadata["config"]["age_values"]}.
Для порядковых и категориальных признаков перебраны допустимые значения, кроме исходного.
Совпадающие варианты удалены.

Анализируются calibrated PD, pd_zone и recommendation с reasons. Пороги:
approve при PD < {metadata["thresholds"]["approve"]}; review при
{metadata["thresholds"]["approve"]} ≤ PD ≤ {metadata["thresholds"]["reject"]}; reject при PD > {metadata["thresholds"]["reject"]}.
Recommendation получена из API, а не рассчитана по этим порогам.
Среднее |ΔPD| — среднее по вариантам внутри каждой базы, затем среднее по базам.
Доли смены зоны рассчитаны по валидным парам PD; доли смены рекомендации — по успешным парам рекомендаций.

Этот отчёт сформирован только из сохранённых файлов; ML API повторно не вызывался.

## Основные результаты

- Изменений pd_zone: **{zone_changes}** ({zone_changes / total:.2%} всех вариантов).
- Изменений recommendation: **{rec_changes}** ({rec_changes / total:.2%} всех вариантов).
- HTTP/API errors при скоринге вариантов: **{errors}**; ошибок формата ответа: **{response_errors}**.
- Ошибок API/ответа на этапе отбора баз: **{screening_errors}**.
- Топ по среднему |ΔPD|: {top_description}.

{(chr(10) * 2).join(ranking_text)}

Три рейтинга независимы; строки с равными значениями сохраняют исходный порядок CSV.
Числовые значения в таблицах округлены, исходная точность сохранена в CSV.

## Чувствительность PD

![Среднее абсолютное изменение PD по признакам](figures/mean_abs_delta_pd.png)

Наибольшая чувствительность PD к изменению признака наблюдается для {top_description}.
Значения выражены в единицах вероятности: например, 0.10 соответствует 10 процентным пунктам PD.
Это чувствительность к выбранному перебору значений, а не feature importance.
Полный перебор категорий и локальные изменения числовых признаков охватывают разный масштаб изменений.

## Чувствительность итогового решения

![Чувствительность итоговой рекомендации](figures/recommendation_change_share.png)

![Чувствительность зоны риска](figures/pd_zone_change_share.png)

Зона по PD и итоговая рекомендация измеряются отдельно. Например, для `age`
доля смены pd_zone составляет {float(age["pd_zone_change_share"]):.2%}, а доля смены
recommendation — {float(age["recommendation_change_share"]):.2%}.
Малое изменение PD не исключает смены рекомендации при пересечении границы бизнес-правила.
Автоматическая recommendation не является сохранённым решением кредитного специалиста.

## Показательные переходы

{(chr(10) * 2).join(case_text)}

## Влияние бизнес-правил

{rule_text}

## Ограничения

- Sensitivity analysis не является causal analysis и не доказывает причинное влияние признаков.
- Изменение одного признака при фиксированных остальных может создавать редкие или нереалистичные комбинации.
- Это не классическая feature importance; ранги зависят от баз и стратегии перебора значений.
- Результаты относятся к текущей модели, preprocessing, thresholds и business rules, зафиксированным в run_metadata.json.
- Выборка невелика и включает базы около порогов; частоты переходов не оценивают частоты в реальном потоке.
- `pd=null` не заменяется нулём и не участвует в числовых дельтах.
- {exclusion_text}

## Вывод

{chr(10).join("- " + item for item in conclusions)}

Источники: [сводка](sensitivity_summary.csv), [варианты](sensitivity_results.csv),
[базы](baselines.csv), [кейсы](transition_cases.json), [метаданные](run_metadata.json).
""".replace(f"{total:,}", f"{total:,}".replace(",", " "))
    (run_dir / "REPORT.md").write_text(report, encoding="utf-8")
    example = next((r for r in selected if r["case_type"] == "review->reject"), None)
    example_text = (
        f"`{example['feature']}` {example['base_value']} → {example['variant_value']}: "
        f"PD {example['base_pd']:.4f} → {example['variant_pd']:.4f}; review → reject."
        if example
        else "Кейс review → reject не найден."
    )
    notes = f"""# Этап 5: тезисы для презентации

- Методика: {len(baselines)} базовых заявок, {total} уникальных вариантов; меняем один признак, остальные фиксируем. Скоринг — ML API /predict/batch.
- Измеряем калиброванный PD, зону по порогам 0.083/0.285 и рекомендацию с бизнес-правилами.
- Топ-5 по среднему |ΔPD|: {top_description}.
- Изменений зоны — {zone_changes}, рекомендации — {rec_changes}; ошибок API при скоринге вариантов — {errors}.
- Показательный переход: {example_text}
- Бизнес-правила: {"YOUNG_APPLICANT_REVIEW даёт review при pd_zone=reject; итоговая рекомендация зависит не только от PD." if young else "Подтверждённый пример не найден."}
- Ограничение: это не причинный анализ и не классическая feature importance; результаты зависят от выбранных баз и изменений.
"""
    (run_dir / "PRESENTATION_NOTES.md").write_text(notes, encoding="utf-8")
    print(
        json.dumps(
            {
                "run_dir": str(run_dir),
                "variants": total,
                "pd_zone_changes": zone_changes,
                "recommendation_changes": rec_changes,
                "missing_cases": missing,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "reports/sensitivity/stage5-first-run",
    )
    render(parser.parse_args().run_dir)


if __name__ == "__main__":
    main()
