-- Исходы кредитов: вернул клиент кредит или нет.
-- В жизни заполняется учётной системой через месяцы после выдачи,
-- в демо — scripts/simulate_traffic.py (создаёт таблицу сам, если её нет).
CREATE TABLE IF NOT EXISTS loan_outcomes (
    application_id BIGINT PRIMARY KEY REFERENCES applications(id) ON DELETE CASCADE,
    defaulted      BOOLEAN NOT NULL,
    observed_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
