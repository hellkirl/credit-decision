import { useEffect, useState } from "react";
import { Link, useNavigation, useSearchParams } from "react-router";

import { AppHeader } from "~/components/app-header";
import {
  api,
  EMPTY,
  formatAmount,
  formatDate,
  label,
  recommendationLabels,
  riskLabels,
  statusLabels,
  type ApplicationsPage,
  type ApplicationsStats,
  type Risk,
} from "~/lib/api";
import type { Route } from "./+types/applications";

export function meta() {
  return [{ title: "Кредитные заявки" }];
}

const PAGE_SIZE = 12;

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const params = new URL(request.url).searchParams;
  const query = new URLSearchParams({
    page: params.get("page") ?? "1",
    page_size: String(PAGE_SIZE),
  });
  for (const key of ["search", "status", "risk", "recommendation"]) {
    const value = params.get(key);
    if (value) query.set(key, value);
  }

  try {
    const [list, stats] = await Promise.all([
      api<ApplicationsPage>(`/applications?${query}`),
      api<ApplicationsStats>("/applications/stats"),
    ]);
    return { list, stats, error: null };
  } catch (error) {
    if (error instanceof Response) throw error;
    return { list: null, stats: null, error: "Не удалось загрузить заявки" };
  }
}

export function HydrateFallback() {
  return <div className="min-h-screen bg-[#F5F6F9]" />;
}

const riskStyles: Record<Risk, string> = {
  low: "bg-[#E8F9E1] text-[#3DC312]",
  medium: "bg-[#FFF0E3] text-[#F07A1A]",
  high: "bg-[#FFE3E3] text-[#E20D0D]",
};


function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Record<string, string>;
}) {
  return (
    <label className="block">
      <span className="mb-[7px] block px-0.5 text-[13px] font-semibold text-[#8F8F8F]">
        {label}
      </span>
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="h-11 w-full appearance-none rounded-lg border border-[#E9E9E9] bg-white px-[15px] pr-10 text-[13px] text-black outline-none focus:border-[#277AFF]"
        >
          <option value="">Все</option>
          {Object.entries(options).map(([key, text]) => (
            <option key={key} value={key}>
              {text}
            </option>
          ))}
        </select>
        <svg
          className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2"
          width="10"
          height="5"
          viewBox="0 0 10 5"
          fill="none"
        >
          <path d="M0 0L5 5L10 0" stroke="black" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    </label>
  );
}

function PageButton({
  label,
  disabled,
  onClick,
  path,
}: {
  label: string;
  disabled: boolean;
  onClick: () => void;
  path: string;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      aria-label={label}
      className="flex h-[30px] w-[30px] items-center justify-center rounded-lg bg-white shadow-[0_2px_6px_0_rgba(23,32,51,0.05)] disabled:bg-[#FBFBFB] disabled:shadow-none"
    >
      <svg width="5" height="10" viewBox="0 0 5 10" fill="none">
        <path
          d={path}
          stroke={disabled ? "#D4D4D4" : "#8F8F8F"}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </button>
  );
}

export default function Applications({ loaderData }: Route.ComponentProps) {
  const { list, stats, error } = loaderData;
  const [searchParams, setSearchParams] = useSearchParams();
  const navigation = useNavigation();
  const loading = navigation.state === "loading";

  const page = list?.page ?? 1;
  const pageCount = list ? Math.max(1, Math.ceil(list.total / list.page_size)) : 1;

  const setParam = (key: string, value: string) =>
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (value) next.set(key, value);
        else next.delete(key);
        if (key !== "page") next.delete("page");
        return next;
      },
      { replace: key !== "page" },
    );

  // Debounce the search box so we don't hit the backend on every keystroke.
  const [search, setSearch] = useState(searchParams.get("search") ?? "");
  useEffect(() => {
    const q = search.trim().replace(/^#/, "");
    if (q === (searchParams.get("search") ?? "")) return;
    const timer = setTimeout(() => setParam("search", q), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const statCards = [
    { label: "Всего заявок", value: stats?.total, note: "За текущий период", color: "text-black" },
    { label: "Новые", value: stats?.new, note: "Требуют обработки", color: "text-[#277AFF]" },
    { label: "На ручной проверке", value: stats?.manual_review, note: "Ожидают решения", color: "text-[#F07A1A]" },
    { label: "Одобрены", value: stats?.approved, note: "Решения приняты", color: "text-[#3DC312]" },
    { label: "Отклонены", value: stats?.rejected, note: "Решения приняты", color: "text-[#E20D0D]" },
  ];

  return (
    <div className="min-h-screen bg-[#F5F6F9] text-black">
      <AppHeader className="sm:px-[37px]">
        <span className="text-xl font-bold">Кредитное решение</span>
      </AppHeader>

      <main className="px-4 py-8 sm:px-[37px]">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h1 className="text-2xl font-bold sm:text-[32px]">Кредитные заявки</h1>
          <Link
            to="/applications/new"
            className="flex h-[42px] items-center rounded-md bg-[#277AFF] px-[17px] text-[15px] font-bold text-white hover:bg-[#1f68db]"
          >
            Новая заявка
          </Link>
        </div>

        <section className="mt-7 grid grid-cols-1 gap-3 min-[480px]:grid-cols-2 sm:gap-[17px] lg:grid-cols-3 xl:grid-cols-5">
          {statCards.map((s) => (
            <div
              key={s.label}
              className="rounded-lg bg-white p-5 shadow-[0_2px_6px_0_rgba(23,32,51,0.05)]"
            >
              <div className="text-[13px] text-[#4A4A4A]">{s.label}</div>
              <div className={`mt-[14px] text-[32px] font-bold leading-[39px] ${s.color}`}>
                {s.value ?? "—"}
              </div>
              <div className="mt-[14px] text-[13px] text-[#4A4A4A]">{s.note}</div>
            </div>
          ))}
        </section>

        <section className="mt-9 grid gap-4 sm:grid-cols-2 lg:[grid-template-columns:minmax(0,1fr)_193px_193px_193px]">
          <label className="block">
            <span className="mb-[7px] block px-0.5 text-[13px] font-semibold text-[#8F8F8F]">
              Поиск
            </span>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Поиск по ID или ФИО"
              className="h-11 w-full rounded-lg border border-[#E9E9E9] bg-white px-[15px] text-[13px] outline-none placeholder:text-[#B2B2B2] focus:border-[#277AFF]"
            />
          </label>
          <Select
            label="Статус"
            value={searchParams.get("status") ?? ""}
            onChange={(v) => setParam("status", v)}
            options={statusLabels}
          />
          <Select
            label="Уровень риска"
            value={searchParams.get("risk") ?? ""}
            onChange={(v) => setParam("risk", v)}
            options={riskLabels}
          />
          <Select
            label="Рекомендация системы"
            value={searchParams.get("recommendation") ?? ""}
            onChange={(v) => setParam("recommendation", v)}
            options={recommendationLabels}
          />
        </section>

        <section
          className={`mt-7 overflow-x-auto rounded-lg bg-white shadow-[0_2px_6px_0_rgba(23,32,51,0.05)] transition-opacity ${loading ? "opacity-60" : ""}`}
        >
          <table className="w-full min-w-[1000px] text-left text-[13px]">
            <thead>
              <tr className="h-9 bg-[#FBFBFB] text-black">
                {["ID Заявки", "Заёмщик", "Сумма кредита", "Уровень риска", "Рекомендация системы", "Статус", "Дата", "Действие"].map(
                  (h) => (
                    <th key={h} className="px-3 font-semibold first:pl-3">
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {list?.items.map((a) => (
                <tr key={a.id} className="h-[36.5px] border-t border-[#F0F0F0]">
                  <td className="px-3">#{a.id}</td>
                  <td className="px-3">{a.borrower ?? EMPTY}</td>
                  <td className="px-3">{formatAmount(a.amount)}</td>
                  <td className="px-3">
                    {a.risk ? (
                      <span
                        className={`inline-block rounded-full px-[14px] py-0.5 text-xs font-semibold ${riskStyles[a.risk]}`}
                      >
                        {riskLabels[a.risk]}
                      </span>
                    ) : (
                      EMPTY
                    )}
                  </td>
                  <td className="px-3">{label(recommendationLabels, a.recommendation)}</td>
                  <td className="px-3">{statusLabels[a.status]}</td>
                  <td className="px-3">{formatDate(a.created_at)}</td>
                  <td className="px-3">
                    <Link
                      to={`/applications/${a.id}`}
                      className="flex h-6 w-20 items-center justify-center rounded-md border border-black/10 bg-white text-xs font-semibold hover:bg-[#F5F6F9]"
                    >
                      Открыть
                    </Link>
                  </td>
                </tr>
              ))}
              {(error || list?.items.length === 0) && (
                <tr>
                  <td
                    colSpan={8}
                    className={`px-3 py-8 text-center ${error ? "text-[#E20D0D]" : "text-[#8F8F8F]"}`}
                  >
                    {error ?? "Заявки не найдены"}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </section>

        <div className="mt-8 flex items-center justify-end gap-3 text-[13px] text-[#8F8F8F]">
          <PageButton
            label="Назад"
            disabled={page <= 1}
            onClick={() => setParam("page", String(page - 1))}
            path="M5 0L0 5L5 10"
          />
          <span>
            {page} из {pageCount}
          </span>
          <PageButton
            label="Вперёд"
            disabled={page >= pageCount}
            onClick={() => setParam("page", String(page + 1))}
            path="M0 10L5 5L0 0"
          />        </div>
      </main>
    </div>
  );
}
