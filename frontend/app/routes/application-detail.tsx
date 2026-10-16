import { useEffect, useState, type ReactNode } from "react";
import { Link, redirect, useFetcher } from "react-router";

import { AppHeader } from "~/components/app-header";
import {
  api,
  ApiError,
  checkingStatusLabels,
  count,
  creditHistoryLabels,
  EMPTY,
  formatAmount,
  formatPercent,
  housingLabels,
  jobLabels,
  label,
  maritalStatusLabels,
  months,
  propertyLabels,
  purposeLabels,
  recommendationLabels,
  riskLabels,
  savingsLabels,
  statusLabels,
  years,
  yesNo,
  type ApplicationDetail as Application,
  type Decision,
  type DecisionInput,
  type Recommendation,
  type Risk,
} from "~/lib/api";
import type { Route } from "./+types/application-detail";

export function meta({ params }: Route.MetaArgs) {
  return [{ title: `Заявка #${params.id}` }];
}

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  try {
    return { application: await api<Application>(`/applications/${params.id}`), error: null };
  } catch (error) {
    if (error instanceof Response) throw error;
    const notFound = error instanceof ApiError && error.status === 404;
    return {
      application: null,
      error: notFound ? "Заявка не найдена" : "Не удалось загрузить заявку",
    };
  }
}

export async function clientAction({ params, request }: Route.ClientActionArgs) {
  const form = await request.formData();
  if (form.get("intent") === "delete") {
    try {
      await api(`/applications/${params.id}`, { method: "DELETE" });
      return redirect("/applications");
    } catch (error) {
      if (error instanceof Response) throw error;
      return { ok: false, error: "Не удалось удалить черновик" };
    }
  }

  const body: DecisionInput = {
    decision: form.get("decision") as Decision,
    reason: String(form.get("reason") ?? ""),
  };
  try {
    await api(`/applications/${params.id}/decision`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    return { ok: true, error: null };
  } catch (error) {
    if (error instanceof Response) throw error;
    return { ok: false, error: "Не удалось сохранить решение" };
  }
}

export function HydrateFallback() {
  return <div className="min-h-screen bg-[#F5F6F9]" />;
}

const riskColors: Record<Risk, string> = {
  low: "text-[#3DC312]",
  medium: "text-[#F07A1A]",
  high: "text-[#E20D0D]",
};

const card = "rounded-[7px] bg-white p-[15px]";

function Card({ title, rows }: { title: string; rows: [string, string][] }) {
  return (
    <section className={card}>
      <h3 className="text-[15px] font-semibold leading-[130%]">{title}</h3>
      <dl className="mt-[22px] space-y-[9px] text-[13px] text-[#4A4A4A]">
        {rows.map(([k, v]) => (
          <div key={k} className="flex flex-wrap justify-between gap-x-4 gap-y-0.5">
            <dt>{k}</dt>
            <dd className="text-right font-semibold">{v}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function Summary({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="text-[13px] text-[#4A4A4A]">{label}</div>
      <div className="mt-2 text-base font-semibold">{children}</div>
    </div>
  );
}

function BackLink() {
  return (
    <Link to="/applications" className="flex items-center gap-2.5 text-sm font-semibold text-[#277AFF]">
      <svg width="4" height="8" viewBox="0 0 4 8" fill="none">
        <path d="M4 0L0 3.97L4 7.93" stroke="#277AFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      К списку заявок
    </Link>
  );
}

export default function ApplicationDetail({ loaderData, params }: Route.ComponentProps) {
  const { application: a, error } = loaderData;

  return (
    <div className="min-h-screen bg-[#F5F6F9] text-black">
      <AppHeader>
        <BackLink />
        <span className="text-xl font-bold">Заявка #{params.id}</span>
      </AppHeader>

      {a ? (
        <ApplicationView a={a} />
      ) : (
        <main className="px-4 py-16 text-center text-[#8F8F8F] sm:px-12">{error}</main>
      )}
    </div>
  );
}

function ApplicationView({ a }: { a: Application }) {
  return (
    <main className="mx-auto max-w-[1440px] px-4 py-9 sm:px-12">
      <section className="rounded-[7px] bg-white px-4 py-[22px] sm:px-[25px]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <h1 className="text-2xl font-bold">{a.borrower ?? EMPTY}</h1>
          <span className="text-[13px] text-[#4A4A4A]">
            {statusLabels[a.status]} · Клиент ID {a.client_id}
          </span>
        </div>
        <div className="mt-4 flex flex-wrap gap-x-10 gap-y-4">
          <Summary label="Сумма кредита">{formatAmount(a.amount)}</Summary>
          <Summary label="Срок кредита">{months(a.term_months)}</Summary>
          <Summary label="Цель кредита">{label(purposeLabels, a.purpose)}</Summary>
        </div>
        <ApplicationActions a={a} />
      </section>

      {a.status === "draft" || !a.risk || !a.recommendation ? (
        <section className="mt-5 rounded-[7px] border border-[#E6E9F2] bg-[#F7F8FD] p-5 text-sm text-[#4A4A4A]">
          Черновик: заявка ещё не отправлена на оценку системой.
        </section>
      ) : (
        <Scoring a={a} risk={a.risk} recommendation={a.recommendation} />
      )}

      <h2 className="mb-4 mt-8 text-2xl font-bold sm:mb-6 sm:mt-10">Данные заявки</h2>

      <div className="grid items-start gap-5 lg:grid-cols-2">
        <div className="space-y-5">
          <Card
            title="Персональные данные"
            rows={[
              ["Возраст", years(a.age)],
              ["Семейное положение", label(maritalStatusLabels, a.marital_status)],
              ["Жилье", label(housingLabels, a.housing)],
              ["Срок проживания", years(a.residence_years)],
              ["Наиболее ценное имущество", label(propertyLabels, a.property)],
              ["Количество иждивенцев", count(a.dependents)],
              ["Телефон", a.phone == null ? EMPTY : a.phone ? "Подтвержден" : "Нет"],
              ["Иностранный работник", yesNo(a.foreign_worker)],
            ]}
          />
          <Card
            title="Занятость"
            rows={[
              ["Профессия", label(jobLabels, a.job)],
              ["Стаж работы", months(a.employment_months)],
            ]}
          />
        </div>
        <div className="space-y-5">
          <Card
            title="Кредит"
            rows={[
              ["Сумма кредита", formatAmount(a.amount)],
              ["Срок", months(a.term_months)],
              ["Цель", label(purposeLabels, a.purpose)],
              [
                "Доля платежа от располагаемого дохода",
                a.installment_rate == null ? EMPTY : `${String(a.installment_rate).replace(".", ",")} %`,
              ],
            ]}
          />
          <Card
            title="Кредитная история"
            rows={[
              ["Кредитная история", label(creditHistoryLabels, a.credit_history)],
              ["Другие варианты рассрочки", yesNo(a.other_installment_plans)],
            ]}
          />
          <Card
            title="Финансовое положение"
            rows={[
              ["Статус текущего счёта", label(checkingStatusLabels, a.checking_status)],
              ["Сбережения", label(savingsLabels, a.savings)],
              ["Количество действующих кредитов", count(a.existing_credits)],
              ["Другие должники / поручители", yesNo(a.other_debtors)],
            ]}
          />
        </div>
      </div>

      {a.status !== "draft" && a.risk && a.recommendation && (
        <DecisionForm
          a={a}
          summary={`${recommendationLabels[a.recommendation]} - ${riskLabels[a.risk]} риск`}
        />
      )}
    </main>
  );
}

function ApplicationActions({ a }: { a: Application }) {
  const fetcher = useFetcher<typeof clientAction>();
  const [confirming, setConfirming] = useState(false);
  const deleting = fetcher.state !== "idle";
  const isDraft = a.status === "draft";

  if (a.status === "completed") return null;

  return (
    <div className="mt-5 flex flex-wrap items-center justify-end gap-3">
      {fetcher.state === "idle" && fetcher.data?.error && (
        <span className="text-[13px] text-[#E20D0D]">{fetcher.data.error}</span>
      )}
      {isDraft && (
        <button
          type="button"
          onClick={() => setConfirming(true)}
          disabled={deleting}
          className="h-[34px] rounded-[5px] border border-[#EBABAB] bg-white px-3.5 text-[13px] font-bold text-[#E20D0D] hover:bg-[#FFF5F5] disabled:opacity-50"
        >
          Удалить черновик
        </button>
      )}
      <Link
        to={`/applications/${a.id}/edit`}
        className="flex h-[34px] items-center rounded-[5px] border border-black/10 bg-white px-3.5 text-[13px] font-bold hover:bg-[#FBFBFB]"
      >
        {isDraft ? "Редактировать черновик" : "Редактировать"}
      </Link>

      {confirming && (
        <ConfirmDialog
          title="Удалить черновик?"
          text={`Черновик заявки #${a.id} будет удалён без возможности восстановления`}
          confirmLabel="Удалить"
          busy={deleting}
          onCancel={() => setConfirming(false)}
          onConfirm={() => fetcher.submit({ intent: "delete" }, { method: "post" })}
        />
      )}
    </div>
  );
}

function Scoring({ a, risk, recommendation }: { a: Application; risk: Risk; recommendation: Recommendation }) {
  const riskColor = riskColors[risk];
  const highlight = (level: Risk) => (risk === level ? `font-semibold ${riskColor}` : "");

  return (
    <section className="mt-5 grid gap-5 lg:grid-cols-2 lg:gap-[30px]">
      <div className="rounded-[7px] border border-[#E6E9F2] bg-[#F7F8FD] p-[14px] shadow-[0_2px_6px_0_rgba(23,32,51,0.05)]">
        <div className="text-sm">
          Рекомендация системы: <b>{recommendationLabels[recommendation]}</b>
        </div>
        <div className="mt-3 grid gap-4 sm:grid-cols-2 sm:gap-[28px]">
          <div className="rounded-lg bg-white p-5">
            <div className="text-[13px] text-[#4A4A4A]">Вероятность дефолта</div>
            <div className={`mt-2 text-[32px] font-bold leading-[39px] ${riskColor}`}>
              {formatPercent(a.default_probability)}
            </div>
            <div className={`mt-1 text-base font-semibold ${riskColor}`}>{riskLabels[risk]} риск</div>
          </div>
          {a.thresholds && (
            <div className="rounded-lg bg-white p-5 text-[13px] leading-[21px] text-[#4A4A4A]">
              <div className="mb-1 font-semibold text-black">Пороги принятия решения:</div>
              <div className={highlight("low")}>Одобрение &lt; {formatPercent(a.thresholds.approve)}</div>
              <div className={highlight("medium")}>
                Ручная проверка {formatPercent(a.thresholds.approve)}-{formatPercent(a.thresholds.reject)}
              </div>
              <div className={highlight("high")}>Отклонение &gt; {formatPercent(a.thresholds.reject)}</div>
            </div>
          )}
        </div>
      </div>

      <div className="rounded-[7px] border border-[#F5C79B] bg-[#FFF5EE] p-5">
        <div className="text-sm font-semibold">Сработавшие правила:</div>
        {a.triggered_rules.length > 0 ? (
          <ul className="mt-4 space-y-2 text-sm">
            {a.triggered_rules.map((rule) => (
              <li key={rule}>{rule}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-4 text-sm text-[#4A4A4A]">Нет</p>
        )}
      </div>
    </section>
  );
}

function DecisionForm({ a, summary }: { a: Application; summary: string }) {
  const fetcher = useFetcher<typeof clientAction>();
  const [decision, setDecision] = useState<Decision | null>(a.decision?.decision ?? null);
  const [reason, setReason] = useState(a.decision?.reason ?? "");
  const [confirming, setConfirming] = useState(false);
  const saving = fetcher.state !== "idle";

  useEffect(() => {
    if (fetcher.state === "idle" && fetcher.data) setConfirming(false);
  }, [fetcher.state, fetcher.data]);

  const confirm = () => {
    if (!decision) return;
    fetcher.submit({ decision, reason: reason.trim() }, { method: "post" });
  };

  return (
    <section className="mt-8 rounded-[7px] bg-white p-4 sm:p-[25px]">
      <h2 className="text-2xl font-bold">Решение специалиста</h2>
      <p className="mt-3 text-[13px] text-[#4A4A4A]">Система рекомендует: {summary}</p>
      <div className="mt-5 flex flex-wrap gap-3 sm:gap-5">
        <button
          type="button"
          onClick={() => setDecision("approve")}
          className={`h-9 rounded-md px-3.5 text-[13px] font-bold text-[#2F6B10] bg-[#BFE5A8] ${
            decision === "approve" ? "ring-2 ring-[#3DC312]" : ""
          }`}
        >
          Одобрить
        </button>
        <button
          type="button"
          onClick={() => setDecision("reject")}
          className={`h-9 rounded-md px-3.5 text-[13px] font-bold text-[#7A1010] bg-[#EBABAB] ${
            decision === "reject" ? "ring-2 ring-[#E20D0D]" : ""
          }`}
        >
          Отклонить
        </button>
      </div>
      <label className="mt-5 block">
        <span className="text-sm font-semibold">Обоснование решения</span>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Укажите причины решения специалиста"
          className="mt-3 h-[82px] w-full resize-none rounded-[5px] border border-[#B2B2B2] bg-white p-[10px] text-[13px] outline-none placeholder:text-[#B2B2B2] focus:border-[#277AFF]"
        />
      </label>
      <div className="mt-5 flex flex-wrap items-center justify-end gap-4">
        {fetcher.state === "idle" && fetcher.data && (
          <span className={`text-[13px] ${fetcher.data.ok ? "text-[#3DC312]" : "text-[#E20D0D]"}`}>
            {fetcher.data.ok ? "Решение сохранено" : fetcher.data.error}
          </span>
        )}
        <button
          type="button"
          onClick={() => setConfirming(true)}
          disabled={!decision || !reason.trim() || saving}
          className="h-[42px] w-full rounded-md sm:w-auto bg-[#277AFF] px-[18px] text-[15px] font-bold text-white hover:bg-[#1f68db] disabled:cursor-not-allowed disabled:opacity-50"
        >
          Сохранить решение
        </button>
      </div>

      {confirming && decision && (
        <ConfirmDialog
          text={`Вы собираетесь ${decision === "approve" ? "одобрить" : "отклонить"} заявку #${a.id}`}
          busy={saving}
          onCancel={() => setConfirming(false)}
          onConfirm={confirm}
        />
      )}
    </section>
  );
}

function ConfirmDialog({
  title = "Подтвердить решение?",
  text,
  confirmLabel = "Подтвердить",
  busy,
  onCancel,
  onConfirm,
}: {
  title?: string;
  text: string;
  confirmLabel?: string;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onCancel();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4"
      onClick={onCancel}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        className="w-full max-w-[528px] rounded-2xl bg-white p-5 sm:p-[31px]"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 id="confirm-title" className="text-xl font-bold">
          {title}
        </h3>
        <p className="mt-4 text-[13px] text-[#4A4A4A]">{text}</p>
        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="h-[42px] rounded-md border border-black/10 bg-white px-[18px] text-[13px] font-bold hover:bg-[#F5F6F9]"
          >
            Отмена
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            autoFocus
            className="h-[42px] rounded-md bg-[#277AFF] px-[18px] text-[15px] font-bold text-white hover:bg-[#1f68db] disabled:opacity-50"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
