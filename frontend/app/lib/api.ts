import { clearToken, getToken, loginRedirect } from "./auth";
import type { components, operations } from "./schema";

// All API types come from backend/api/openapi/openapi.yaml via `npm run api:types`
// (generated into ./schema.d.ts). Do not hand-write response shapes here.

type Schemas = components["schemas"];

export type User = Schemas["User"];
export type LoginRequest = Schemas["LoginRequest"];
export type TokenResponse = Schemas["TokenResponse"];
export type ApplicationSummary = Schemas["ApplicationSummary"];
export type ApplicationsPage = Schemas["ApplicationsPage"];
export type ApplicationsStats = Schemas["ApplicationsStats"];
export type ApplicationInput = Schemas["ApplicationInput"];
export type ApplicationDetail = Schemas["ApplicationDetail"];
export type DecisionInput = Schemas["DecisionInput"];
export type CreatedApplication =
  operations["createApplication"]["responses"]["201"]["content"]["application/json"];

export type Risk = Schemas["Risk"];
export type Recommendation = Schemas["Recommendation"];
export type Status = Schemas["Status"];
export type Decision = Schemas["Decision"];

// Display labels for the spec's enums. `satisfies` makes a new enum value in
// the spec a compile error here until it gets a label.

export const riskLabels = {
  low: "Низкий",
  medium: "Средний",
  high: "Высокий",
} satisfies Record<Risk, string>;
export const recommendationLabels = {
  approve: "Одобрить",
  review: "Проверить дополнительно",
  reject: "Отклонить",
} satisfies Record<Recommendation, string>;
export const statusLabels = {
  draft: "Черновик",
  new: "Новая",
  manual_review: "На ручной проверке",
  pending_confirmation: "На подтверждении",
  completed: "Завершена",
} satisfies Record<Status, string>;
export const maritalStatusLabels = {
  single: "Холост / не замужем",
  married: "Женат / замужем",
  divorced: "Разведён(а)",
  widowed: "Вдовец / вдова",
} satisfies Record<Schemas["MaritalStatus"], string>;
export const housingLabels = {
  own: "Собственность",
  rent: "Аренда",
  free: "Бесплатное проживание",
} satisfies Record<Schemas["Housing"], string>;
export const propertyLabels = {
  real_estate: "Недвижимость",
  savings_insurance: "Сбережения / страхование жизни",
  car: "Автомобиль",
  none: "Нет",
} satisfies Record<Schemas["Property"], string>;
export const jobLabels = {
  unemployed: "Безработный",
  unskilled: "Неквалифицированный работник",
  skilled: "Квалифицированный специалист",
  management: "Руководитель / высококвалифицированный",
} satisfies Record<Schemas["Job"], string>;
export const purposeLabels = {
  new_car: "Новый автомобиль",
  used_car: "Подержанный автомобиль",
  furniture: "Мебель / оборудование",
  electronics: "Техника",
  repairs: "Ремонт жилья",
  education: "Образование",
  retraining: "Переподготовка",
  business: "Бизнес",
  other: "Другое",
} satisfies Record<Schemas["Purpose"], string>;
export const creditHistoryLabels = {
  no_credits: "Кредитов не было",
  all_paid: "Все кредиты погашались вовремя",
  existing_paid: "Текущие кредиты погашаются вовремя",
  delayed: "Были просрочки",
  critical: "Критическая",
} satisfies Record<Schemas["CreditHistory"], string>;
export const checkingStatusLabels = {
  none: "Нет счёта",
  lt_0: "< 0 DM",
  "0_200": "0–200 DM",
  ge_200: "≥ 200 DM",
} satisfies Record<Schemas["CheckingStatus"], string>;
export const savingsLabels = {
  unknown: "Нет / неизвестно",
  lt_100: "< 100 DM",
  "100_500": "100–500 DM",
  "500_1000": "500–1000 DM",
  ge_1000: "≥ 1000 DM",
} satisfies Record<Schemas["Savings"], string>;
export const yesNoLabels = { false: "Нет", true: "Да" } as const;

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  if (!token) throw loginRedirect(window.location.href);

  const res = await fetch(`/api${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...init?.headers,
    },
  });
  if (res.status === 401) {
    clearToken();
    throw loginRedirect(window.location.href);
  }
  if (!res.ok) throw new ApiError(res.status, path);
  return res.status === 204 ? (undefined as T) : res.json();
}

export class ApiError extends Error {
  constructor(
    public status: number,
    path: string,
  ) {
    super(`${path}: ${status}`);
  }
}

// Formatting. Every helper accepts null (drafts) and renders it as a dash.

export const EMPTY = "—";

export function label<K extends string>(labels: Record<K, string>, value: K | null | undefined) {
  return value == null ? EMPTY : labels[value];
}

export const yesNo = (value: boolean | null) => (value == null ? EMPTY : yesNoLabels[`${value}`]);

const amountFormatter = new Intl.NumberFormat("ru-RU", {
  style: "currency",
  currency: "RUB",
  maximumFractionDigits: 0,
});
export const formatAmount = (value: number | null) => (value == null ? EMPTY : amountFormatter.format(value));

const dateFormatter = new Intl.DateTimeFormat("ru-RU");
export const formatDate = (value: string) => dateFormatter.format(new Date(value));

export const formatPercent = (fraction: number | null) =>
  fraction == null ? EMPTY : `${(fraction * 100).toFixed(1).replace(".", ",")}%`;

const pluralRules = new Intl.PluralRules("ru-RU");
function plural(n: number | null, forms: { one: string; few: string; many: string }) {
  if (n == null) return EMPTY;
  const form = pluralRules.select(n);
  return `${n} ${form === "one" ? forms.one : form === "few" ? forms.few : forms.many}`;
}
export const years = (n: number | null) => plural(n, { one: "год", few: "года", many: "лет" });
export const months = (n: number | null) => plural(n, { one: "месяц", few: "месяца", many: "месяцев" });
export const count = (n: number | null) => (n == null ? EMPTY : String(n));
