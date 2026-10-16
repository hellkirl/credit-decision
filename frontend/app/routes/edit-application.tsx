import { Link, redirect, useNavigation } from "react-router";

import { AppHeader } from "~/components/app-header";
import { ApplicationForm, parseApplicationForm } from "~/components/application-form";
import { api, ApiError, type ApplicationDetail } from "~/lib/api";
import type { Route } from "./+types/edit-application";

export function meta({ params }: Route.MetaArgs) {
  return [{ title: `Редактирование заявки #${params.id}` }];
}

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  try {
    const application = await api<ApplicationDetail>(`/applications/${params.id}`);
    if (application.status === "completed") throw redirect(`/applications/${params.id}`);
    return { application, error: null };
  } catch (error) {
    if (error instanceof Response) throw error;
    const notFound = error instanceof ApiError && error.status === 404;
    return { application: null, error: notFound ? "Заявка не найдена" : "Не удалось загрузить заявку" };
  }
}

export async function clientAction({ params, request }: Route.ClientActionArgs) {
  const body = parseApplicationForm(await request.formData());
  try {
    await api(`/applications/${params.id}`, { method: "PUT", body: JSON.stringify(body) });
    return redirect(`/applications/${params.id}`);
  } catch (error) {
    if (error instanceof Response) throw error;
    const status = error instanceof ApiError ? error.status : 0;
    return {
      error:
        status === 400
          ? "Проверьте правильность заполнения полей"
          : status === 409
            ? "Эту заявку больше нельзя редактировать"
            : "Не удалось сохранить заявку",
    };
  }
}

export function HydrateFallback() {
  return <div className="min-h-screen bg-[#F5F6F9]" />;
}

export default function EditApplication({ loaderData, actionData, params }: Route.ComponentProps) {
  const { application: a, error } = loaderData;
  const navigation = useNavigation();
  const isDraft = a?.status === "draft";

  return (
    <div className="min-h-screen bg-[#F5F6F9] text-black">
      <AppHeader>
        <Link
          to={`/applications/${params.id}`}
          className="flex items-center gap-2.5 text-sm font-semibold text-[#277AFF]"
        >
          <svg width="4" height="8" viewBox="0 0 4 8" fill="none">
            <path d="M4 0L0 3.97L4 7.93" stroke="#277AFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          К заявке
        </Link>
      </AppHeader>

      <main className="mx-auto max-w-[1440px] px-4 py-9 sm:px-12">
        <h1 className="text-2xl font-bold sm:text-[32px]">
          {isDraft ? "Редактирование черновика" : "Редактирование заявки"} #{params.id}
        </h1>
        {a ? (
          <>
            {!isDraft && (
              <p className="mt-3 text-[13px] text-[#4A4A4A]">
                После сохранения заявка будет заново оценена системой.
              </p>
            )}
            <ApplicationForm
              key={a.id}
              initial={a}
              error={actionData?.error}
              submitting={navigation.state === "submitting"}
              allowDraft={isDraft}
              submitLabel={isDraft ? "Отправить на оценку" : "Сохранить и пересчитать"}
              cancelTo={`/applications/${params.id}`}
            />
          </>
        ) : (
          <p className="py-16 text-center text-[#8F8F8F]">{error}</p>
        )}
      </main>
    </div>
  );
}
