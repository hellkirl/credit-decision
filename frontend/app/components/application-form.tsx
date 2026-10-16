import type { ReactNode } from "react";
import { Form, Link } from "react-router";

import {
  checkingStatusLabels,
  creditHistoryLabels,
  housingLabels,
  jobLabels,
  maritalStatusLabels,
  propertyLabels,
  purposeLabels,
  savingsLabels,
  yesNoLabels,
  type ApplicationDetail,
  type ApplicationInput,
} from "~/lib/api";

export function parseApplicationForm(form: FormData): ApplicationInput {
  const str = (key: string) => String(form.get(key) ?? "").trim();
  // Drafts skip browser validation, so empty fields go out as null.
  const num = (key: string) => (str(key) === "" ? null : Number(str(key).replace(",", ".")));
  const choice = <K extends keyof ApplicationInput>(key: K) => (str(key) || null) as ApplicationInput[K];
  const bool = (key: string) => (str(key) === "" ? null : str(key) === "true");

  return {
    borrower: str("borrower"),
    dependents: num("dependents"),
    housing: choice("housing"),
    age: num("age"),
    phone: bool("phone"),
    residence_years: num("residence_years"),
    marital_status: choice("marital_status"),
    foreign_worker: bool("foreign_worker"),
    property: choice("property"),
    job: choice("job"),
    employment_months: num("employment_months"),
    amount: num("amount"),
    term_months: num("term_months"),
    purpose: choice("purpose"),
    installment_rate: num("installment_rate"),
    checking_status: choice("checking_status"),
    other_installment_plans: bool("other_installment_plans"),
    savings: choice("savings"),
    other_debtors: bool("other_debtors"),
    credit_history: choice("credit_history"),
    existing_credits: num("existing_credits"),
    draft: str("intent") === "draft",
  };
}

const control =
  "h-[34px] w-full rounded-[5px] border border-[#B2B2B2] bg-white px-[15px] text-[13px] text-black outline-none placeholder:text-[#B2B2B2] focus:border-[#277AFF]";

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-[7px] block text-[13px] font-semibold">{label}</span>
      {children}
    </label>
  );
}

function TextField({
  label,
  name,
  ...props
}: { label: string; name: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <Field label={label}>
      <input name={name} required className={control} {...props} />
    </Field>
  );
}

function SelectField({
  label,
  name,
  options,
  defaultValue = "",
}: {
  label: string;
  name: string;
  options: Record<string, string>;
  defaultValue?: string;
}) {
  return (
    <Field label={label}>
      <div className="relative">
        <select
          name={name}
          required
          defaultValue={defaultValue}
          className={`${control} appearance-none pr-10 invalid:text-[#B2B2B2]`}
        >
          {!defaultValue && (
            <option value="" disabled>
              Выберите
            </option>
          )}
          {Object.entries(options).map(([key, text]) => (
            <option key={key} value={key} className="text-black">
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
    </Field>
  );
}

function Section({ title, className, children }: { title: string; className: string; children: ReactNode }) {
  return (
    <section className="rounded-[7px] bg-white p-4 sm:px-[18px] sm:py-[22px]">
      <h2 className="text-xl font-bold">{title}</h2>
      <div className={`mt-5 grid gap-x-[13px] gap-y-4 ${className}`}>{children}</div>
    </section>
  );
}

const text = (v: string | number | null | undefined) => (v == null ? "" : String(v));
const yesNo = (v: boolean | null | undefined) => String(v ?? false);

export function ApplicationForm({
  initial,
  error,
  submitting,
  allowDraft,
  submitLabel,
  cancelTo,
}: {
  initial?: ApplicationDetail;
  error?: string | null;
  submitting: boolean;
  allowDraft: boolean;
  submitLabel: string;
  cancelTo: string;
}) {
  return (
    <Form method="post" className="mt-7 space-y-6">
      <Section title="Клиент" className="sm:grid-cols-2 lg:grid-cols-3">
        <TextField
          label="ФИО"
          name="borrower"
          placeholder="Петров Иван Иванович"
          autoComplete="off"
          defaultValue={text(initial?.borrower)}
        />
        <TextField
          label="Количество иждивенцев"
          name="dependents"
          type="number"
          min={0}
          defaultValue={text(initial?.dependents)}
        />
        <SelectField label="Тип жилья" name="housing" options={housingLabels} defaultValue={text(initial?.housing)} />
        <TextField label="Возраст" name="age" type="number" min={18} max={100} defaultValue={text(initial?.age)} />
        <SelectField label="Телефон" name="phone" options={yesNoLabels} defaultValue={yesNo(initial?.phone)} />
        <TextField
          label="Срок проживания по текущему адресу, лет"
          name="residence_years"
          type="number"
          min={0}
          defaultValue={text(initial?.residence_years)}
        />
        <SelectField
          label="Семейное положение"
          name="marital_status"
          options={maritalStatusLabels}
          defaultValue={text(initial?.marital_status)}
        />
        <SelectField
          label="Иностранный работник"
          name="foreign_worker"
          options={yesNoLabels}
          defaultValue={yesNo(initial?.foreign_worker)}
        />
        <SelectField
          label="Наиболее ценное имущество"
          name="property"
          options={propertyLabels}
          defaultValue={text(initial?.property)}
        />
      </Section>

      <Section title="Занятость" className="sm:grid-cols-2">
        <SelectField
          label="Профессия / Статус занятости"
          name="job"
          options={jobLabels}
          defaultValue={text(initial?.job)}
        />
        <TextField
          label="Стаж работы, месяцев"
          name="employment_months"
          type="number"
          min={0}
          defaultValue={text(initial?.employment_months)}
        />
      </Section>

      <Section title="Кредит" className="sm:grid-cols-2 lg:grid-cols-4">
        <TextField
          label="Сумма кредита, ₽"
          name="amount"
          type="number"
          min={1}
          step={1}
          defaultValue={text(initial?.amount)}
        />
        <TextField
          label="Срок кредита, месяцев"
          name="term_months"
          type="number"
          min={1}
          defaultValue={text(initial?.term_months)}
        />
        <SelectField
          label="Цель кредита"
          name="purpose"
          options={purposeLabels}
          defaultValue={text(initial?.purpose)}
        />
        <TextField
          label="Доля платежа от располагаемого дохода (%)"
          name="installment_rate"
          type="number"
          min={0}
          max={100}
          step={0.1}
          defaultValue={text(initial?.installment_rate)}
        />
      </Section>

      <Section title="Финансовое положение" className="sm:grid-cols-2">
        <SelectField
          label="Статус текущего счета"
          name="checking_status"
          options={checkingStatusLabels}
          defaultValue={text(initial?.checking_status)}
        />
        <SelectField
          label="Другие варианты рассрочки"
          name="other_installment_plans"
          options={yesNoLabels}
          defaultValue={yesNo(initial?.other_installment_plans)}
        />
        <SelectField label="Сбережения" name="savings" options={savingsLabels} defaultValue={text(initial?.savings)} />
        <SelectField
          label="Другие должники / поручители"
          name="other_debtors"
          options={yesNoLabels}
          defaultValue={yesNo(initial?.other_debtors)}
        />
        <SelectField
          label="Кредитная история"
          name="credit_history"
          options={creditHistoryLabels}
          defaultValue={text(initial?.credit_history)}
        />
        <TextField
          label="Количество действующих кредитов"
          name="existing_credits"
          type="number"
          min={0}
          defaultValue={text(initial?.existing_credits)}
        />
      </Section>

      <div className="flex flex-wrap items-center justify-end gap-3 sm:gap-5">
        {error && <span className="text-[13px] text-[#E20D0D]">{error}</span>}
        <Link
          to={cancelTo}
          className="flex h-[34px] items-center rounded-[5px] border border-black/10 bg-white px-3.5 text-[13px] font-bold hover:bg-[#FBFBFB]"
        >
          Отменить
        </Link>
        {allowDraft && (
          <button
            type="submit"
            name="intent"
            value="draft"
            formNoValidate
            disabled={submitting}
            className="h-[34px] rounded-[5px] border border-black/10 bg-white px-3.5 text-[13px] font-bold hover:bg-[#FBFBFB] disabled:opacity-50"
          >
            Сохранить как черновик
          </button>
        )}
        <button
          type="submit"
          name="intent"
          value="submit"
          disabled={submitting}
          className="h-[34px] rounded-[5px] bg-[#277AFF] px-3.5 text-[13px] font-bold text-white hover:bg-[#1f68db] disabled:opacity-50"
        >
          {submitLabel}
        </button>
      </div>
    </Form>
  );
}
