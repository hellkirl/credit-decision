# decision-monitor — метрики решения

Технический блок (задержка, ошибки, запросы) показывает, **работает ли сервис**.
Этот блок показывает, **правильно ли он решает**: не уехали ли данные от обучающих,
совпадает ли PD с реальностью, не страдает ли какая-то группа клиентов.

```
backend ──пишет──> Postgres: applications (журнал решений)
                            loan_outcomes (исходы: вернул / не вернул)
                                  │ читает раз в минуту, окно 30 дней
                                  ▼
                      decision-monitor :9108/metrics ──> Prometheus ──> Grafana
                                  ▲
                      reference/reference.json (эталон: обучающая выборка 800)
```

## Запуск

```bash
docker compose up -d --build                              # основной стек (как раньше)
docker compose --env-file .env -f monitoring/docker-compose.yml up -d --build
```

`--env-file .env` — чтобы мониторинг взял те же `POSTGRES_*` и `RUB_PER_DM`, что и основной
стек (без него compose ищет `.env` в папке `monitoring/`). Проверка: Prometheus
`http://localhost:9090` → Status → Targets, у `decision-monitor` состояние UP.

Папка репозитория должна называться `credit-decision`: от неё зависит имя сети
`credit-decision_service-network`, к которой подключается мониторинг.

Метрики появятся через минуту, но только когда в журнале есть заявки.
Демо-поток (200 тестовых заявок через backend + их исходы):

```bash
docker compose --env-file .env -f monitoring/docker-compose.yml exec decision-monitor \
  python scripts/simulate_traffic.py --mode normal --login <SEED_USER_LOGIN> --password <SEED_USER_PASSWORD>
# через 15+ минут — сдвиг потока в молодых клиентов:
docker compose --env-file .env -f monitoring/docker-compose.yml exec decision-monitor \
  python scripts/simulate_traffic.py --mode young_shift --login ... --password ...
```

Для демо удобно окно `MONITOR_WINDOW=15m` (строкой в корневом `.env`):
тогда второй прогон не смешивается с первым и скачок дрейфа виден чисто.

## Метрики

Все — gauge, кроме `credit_monitor_runs_total` (counter).
**Пересчёт:** раз в 60 с (`MONITOR_INTERVAL_SECONDS`) по заявкам за окно 30 дней (`MONITOR_WINDOW`).
**Экспорт:** pull. Контейнер `decision-monitor` отдаёт `/metrics` на порту 9108,
Prometheus забирает раз в 30 с (job `decision-monitor`). Запрос Prometheus ничего не
считает — он получает последний готовый снимок.

Метки групп: `group_type` / `group`

| group_type | group |
|---|---|
| `all` | `all` |
| `age` | `<=25`, `26-35`, `36-50`, `>50` |
| `marital_status` | `single`, `married`, `divorced`, `widowed` |
| `foreign_worker` | `yes`, `no` |

**Правило n ≥ 30:** если в группе меньше 30 заявок, ряда для неё нет (кроме счётчиков
`credit_monitor_applications` / `credit_outcomes_labeled`). Пустая панель = мало данных, а не ноль.

### Слой 1 — сразу после решения (исходы не нужны)

| Метрика | Метки | Что означает значение |
|---|---|---|
| `credit_monitor_applications` | group_type, group | Сколько заявок в окне (черновики не считаются) |
| `credit_unscored_share` | group_type, group | Доля заявок без PD, 0..1: вне диапазона обучения (`NUMERIC_OUT_OF_RANGE`) или новая категория (`UNSEEN_CATEGORY`). Растёт — данные уходят за пределы модели |
| `credit_zone_share` | group_type, group, zone=`approve`/`review`/`reject` | Доля рекомендаций системы в зоне, 0..1. Это рекомендация **после** правил (молодым reject → review) |
| `credit_pd_mean` | group_type, group | Средний калиброванный PD (по заявкам, где он есть) |
| `credit_feature_psi` | feature = `pd` или имя признака модели (20 шт.) | PSI относительно обучающей выборки. < 0.1 стабильно, 0.1–0.25 заметный сдвиг, > 0.25 сильный. Считается при ≥ 50 заявках в окне |
| `credit_rule_triggered_share` | rule = `YOUNG_APPLICANT_REVIEW`, `NUMERIC_OUT_OF_RANGE`, `UNSEEN_CATEGORY` | Доля заявок, где сработало правило, 0..1 |

### Слой 2 — когда известен исход (таблица `loan_outcomes`)

| Метрика | Метки | Что означает значение |
|---|---|---|
| `credit_outcomes_labeled` | group_type, group | Сколько заявок в окне с известным исходом |
| `credit_calibration_pd_mean` | group_type, group | Средний PD **по тем же** заявкам, у которых известен исход (и есть PD) |
| `credit_calibration_default_rate` | group_type, group | Фактическая доля дефолтов среди них. Хорошая калибровка — две линии рядом |
| `credit_false_reject_rate` | group_type, group | Ложные отказы: доля рекомендаций `reject` среди клиентов, которые на деле вернули кредит, 0..1 |
| `credit_false_reject_gap_pp` | group_type, group (кроме `all`) | Ложные отказы группы минус общий уровень, **в п.п.** Положительное — группе отказывают чаще среднего |

### Служебные

| Метрика | Метки | Что означает |
|---|---|---|
| `credit_monitor_last_success_timestamp_seconds` | — | Unix-время последнего успешного пересчёта |
| `credit_monitor_run_duration_seconds` | — | Сколько длился последний пересчёт |
| `credit_monitor_runs_total` | result=`ok`/`error` | Счётчик пересчётов |
| `credit_monitor_info` | window, reference_model_sha256, reference_built_at | Всегда 1. По какому окну и эталону считаем |

## Панели ML-блока (PromQL)

| Панель | Тип | Запрос | Настройка |
|---|---|---|---|
| Калибровка | Time series | `credit_calibration_pd_mean{group_type="all"}` и `credit_calibration_default_rate{group_type="all"}` | Legend: «PD модели» / «Факт» |
| Калибровка по возрасту | Bar chart | `credit_calibration_pd_mean{group_type="age"}` и `credit_calibration_default_rate{group_type="age"}` | Format: Table, Type: Instant |
| Зоны по возрасту | Bar chart | `credit_zone_share{group_type="age"}` | Stacking: Normal, Unit: Percent (0.0-1.0) |
| Ложные отказы | Bar chart | `credit_false_reject_gap_pp` | Threshold 10, Show thresholds: As lines |
| Дрейф | Bar gauge | `sort_desc(credit_feature_psi)` | Thresholds: зелёный, 0.1 жёлтый, 0.25 красный |
| Дрейф PD во времени | Time series | `credit_feature_psi{feature="pd"}` | Те же пороги, As lines |
| Правила | Time series | `credit_rule_triggered_share` | Unit: Percent (0.0-1.0) |
| Заявки без PD | Stat | `credit_unscored_share{group_type="all"}` | Unit: Percent (0.0-1.0), порог 0.05 |
| Свежесть | Stat | `time() - credit_monitor_last_success_timestamp_seconds` | Unit: seconds, порог 600 |

## Сигналы и действия

Правила — `monitoring/prometheus/alerts.yml`, видны в Prometheus → Alerts.
Дрейф — повод для разбора, **не** для автоматического переобучения.

| Сигнал | Порог | Что делать | Кто |
|---|---|---|---|
| `CreditPdDriftWarning` | PSI(pd) > 0.1, 2 мин | Посмотреть, какие признаки сдвинулись и в каких группах | ML / мониторинг |
| `CreditPdDriftCritical` | PSI(pd) > 0.25, 2 мин | Разбор в течение дня. Если сдвиг из-за ошибки данных — откат версии правил/сервиса. Если клиенты реально другие — расширить ручную проверку до решения о переобучении | ML + риски |
| `CreditFeatureDrift` | PSI(признак) > 0.25 | Отличить: изменился поток клиентов или сломалась передача поля (маппинг, единицы суммы, курс `RUB_PER_DM`) | Разработка + ML |
| `CreditCalibrationGap` | \|PD − факт\| > 5 п.п. при ≥ 200 исходах | Переподобрать Platt (a, b) на свежих исходах, выпустить новую версию калибратора, пересобрать эталон | ML |
| `CreditFalseRejectGap` | группа > среднего на 10 п.п. (n ≥ 30) | Разбор отказов группы (критерий из «Рисков» паспорта), спорные — на ручную проверку | Риски |
| `CreditMonitorStale` | нет пересчёта > 10 мин | Проверить контейнер `credit-decision-monitor` и доступ к базе | Эксплуатация |

## Эталон

`reference/reference.json` — распределения 20 признаков и PD на обучающей выборке (800).
PD эталона — out-of-fold, как при обучении калибратора. В файле записаны хеши модели и
калибратора. **После каждого переобучения** пересобрать:

```bash
ml/venv/bin/python monitoring/decision-monitor/scripts/build_reference.py
```

## Ограничения

- В демо исход известен для всех заявок. В жизни дефолт виден только у **одобренных**:
  для отклонённых его не узнать, поэтому ложные отказы в эксплуатации оцениваются по
  небольшой контрольной выборке, а не по всем отказам.
- **Известный сдвиг с первого дня.** Интерфейс не может выразить часть кодов обучающей
  выборки: `personal_status_sex=4` (пол не собирается), `other_debtors=3`,
  `other_installment_plans=2`, `purpose=5/8`. Поэтому на обычном потоке PSI по
  `personal_status_sex` ≈ 0.65, `other_debtors` ≈ 0.36, `other_installment_plans` ≈ 0.32,
  `purpose` ≈ 0.23 (оценка на тестовых 200), и `CreditFeatureDrift` горит постоянно.
  Это не дрейф клиентов, а расхождение схемы интерфейса и обучающих данных. Решение за
  командой: дополнить интерфейс или переобучить модель на кодах, которые интерфейс умеет
  передавать, и пересобрать эталон.
- Маппинг полей интерфейса в коды модели скопирован из backend
  (`internal/adapters/out/ml/features.go`) в `app/encoding.py`. Меняется там — менять здесь.
- Тесты: `cd monitoring/decision-monitor && python -m pytest tests -q`.
