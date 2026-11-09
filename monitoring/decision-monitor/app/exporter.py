"""decision-monitor: считает метрики решения по журналу и отдаёт их Prometheus.

Цикл: раз в MONITOR_INTERVAL_SECONDS читаем заявки за окно MONITOR_WINDOW из
Postgres -> переводим в коды модели -> считаем метрики (metrics.py) ->
кладём готовый снимок в память. Prometheus приходит на :9108/metrics и
забирает последний снимок. Расчёт и отдача разделены: запрос Prometheus
ничего не считает и базу не трогает.

Запуск: python -m app.exporter (из папки decision-monitor; в Docker — CMD).
"""
from __future__ import annotations

import json
import logging
import threading
import time

from prometheus_client import Counter, Gauge, start_http_server
from prometheus_client.core import REGISTRY, GaugeMetricFamily

from app import config, db
from app.encoding import journal_to_codes
from app.metrics import Snapshot, compute_snapshot

log = logging.getLogger("decision-monitor")

GROUP = ["group_type", "group"]

# Имя -> (описание, метки). Эту же таблицу смотри в METRICS.md.
METRIC_SPECS: dict[str, tuple[str, list[str]]] = {
    "credit_monitor_applications": (
        "Заявок в окне мониторинга (без черновиков)", GROUP),
    "credit_unscored_share": (
        "Доля заявок без PD (вне диапазона обучения или новая категория), 0..1", GROUP),
    "credit_zone_share": (
        "Доля рекомендаций по зонам (approve/review/reject), 0..1", GROUP + ["zone"]),
    "credit_pd_mean": (
        "Средний калиброванный PD заявок в окне", GROUP),
    "credit_feature_psi": (
        "PSI признака или PD относительно обучающей выборки", ["feature"]),
    "credit_rule_triggered_share": (
        "Доля заявок, где сработало правило, 0..1", ["rule"]),
    "credit_outcomes_labeled": (
        "Заявок в окне с известным исходом (вернул/не вернул)", GROUP),
    "credit_calibration_pd_mean": (
        "Средний PD среди заявок с известным исходом", GROUP),
    "credit_calibration_default_rate": (
        "Фактическая доля дефолтов среди заявок с известным исходом", GROUP),
    "credit_false_reject_rate": (
        "Доля рекомендаций reject среди клиентов без дефолта, 0..1", GROUP),
    "credit_false_reject_gap_pp": (
        "Ложные отказы группы минус общий уровень, п.п.", GROUP),
}


class SnapshotCollector:
    """Отдаёт Prometheus последний посчитанный снимок целиком.

    Снимок заменяется одной операцией присваивания, поэтому Prometheus никогда
    не увидит «половину старого, половину нового» расчёта. Ряды, которых нет в
    снимке (например, группа стала меньше 30 заявок), просто пропадают.
    """

    def __init__(self) -> None:
        self.snapshot = Snapshot()

    def collect(self):
        snap = self.snapshot
        for name, (help_text, labels) in METRIC_SPECS.items():
            family = GaugeMetricFamily(name, help_text, labels=labels)
            for lbl, value in snap.samples.get(name, []):
                family.add_metric([lbl[k] for k in labels], value)
            yield family


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = config.load()
    reference = json.loads(settings.reference_path.read_text(encoding="utf-8"))

    collector = SnapshotCollector()
    REGISTRY.register(collector)
    runs = Counter("credit_monitor_runs", "Запуски пересчёта метрик", ["result"])
    last_success = Gauge("credit_monitor_last_success_timestamp_seconds",
                         "Unix-время последнего успешного пересчёта")
    duration = Gauge("credit_monitor_run_duration_seconds", "Длительность последнего пересчёта, с")
    info = Gauge("credit_monitor_info", "Параметры мониторинга (значение всегда 1)",
                 ["window", "reference_model_sha256", "reference_built_at"])
    info.labels(settings.window, reference["model_sha256"], reference["built_at"]).set(1)
    for result in ("ok", "error"):
        runs.labels(result)  # чтобы ряды существовали с нуля

    start_http_server(settings.port)
    log.info("listening on :%d, window=%s, every %ds",
             settings.port, settings.window, settings.interval_seconds)

    stop = threading.Event()
    while not stop.is_set():
        started = time.monotonic()
        try:
            journal = db.load_journal(settings.database_url, settings.window_seconds)
            codes = journal_to_codes(journal, settings.rub_per_dm)
            collector.snapshot = compute_snapshot(
                journal, codes, reference,
                min_group_size=settings.min_group_size,
                min_psi_sample=settings.min_psi_sample,
            )
            runs.labels("ok").inc()
            last_success.set_to_current_time()
            log.info("recomputed: %d applications, %d with outcome",
                     len(journal), int(journal["defaulted"].notna().sum()))
        except Exception:  # база недоступна и т. п. — старый снимок остаётся, ждём следующего круга
            runs.labels("error").inc()
            log.exception("recompute failed")
        duration.set(time.monotonic() - started)
        stop.wait(settings.interval_seconds)


if __name__ == "__main__":
    main()
