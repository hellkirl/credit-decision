import { Link, redirect, useNavigation } from "react-router";

import { AppHeader } from "~/components/app-header";
import { ApplicationForm, parseApplicationForm } from "~/components/application-form";
import { api, ApiError, type CreatedApplication } from "~/lib/api";
import type { Route } from "./+types/new-application";

export function meta() {
  return [{ title: "Новая кредитная заявка" }];
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const body = parseApplicationForm(await request.formData());
  try {
    const { id } = await api<CreatedApplication>("/applications", {
      method: "POST",
      body: JSON.stringify(body),
    });
    return redirect(`/applications/${id}`);
  } catch (error) {
    if (error instanceof Response) throw error;
    const invalid = error instanceof ApiError && error.status === 400;
    return { error: invalid ? "Проверьте правильность заполнения полей" : "Не удалось создать заявку" };
  }
}

export default function NewApplication({ actionData }: Route.ComponentProps) {
  const navigation = useNavigation();

  return (
    <div className="min-h-screen bg-[#F5F6F9] text-black">
      <AppHeader>
        <Link to="/applications" className="flex items-center gap-2.5 text-sm font-semibold text-[#277AFF]">
          <svg width="4" height="8" viewBox="0 0 4 8" fill="none">
            <path d="M4 0L0 3.97L4 7.93" stroke="#277AFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          К списку заявок
        </Link>
      </AppHeader>

      <main className="mx-auto max-w-[1440px] px-4 py-9 sm:px-12">
        <h1 className="text-2xl font-bold sm:text-[32px]">Новая кредитная заявка</h1>
        <ApplicationForm
          error={actionData?.error}
          submitting={navigation.state === "submitting"}
          allowDraft
          submitLabel="Создать заявку"
          cancelTo="/applications"
        />
      </main>
    </div>
  );
}
