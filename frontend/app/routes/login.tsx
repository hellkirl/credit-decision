import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import { getToken, safeRedirect, setToken, type LoginResponse } from "~/lib/auth";

export function meta() {
  return [{ title: "Вход в систему" }];
}

export default function Login() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const target = safeRedirect(searchParams.get("redirect"));
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Already signed in: skip the form.
  useEffect(() => {
    if (getToken()) navigate(target, { replace: true });
  }, []);

  async function handleSubmit(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setLoading(true);

    const form = new FormData(event.currentTarget);
    const body = {
      login: form.get("login"),
      password: form.get("password"),
    };

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        setError(res.status === 401 ? "Неверный логин или пароль" : "Ошибка при входе в систему");
        return;
      }

      setToken((await res.json()) as LoginResponse);
      navigate(target, { replace: true });
    } catch {
      setError("Ошибка при входе в систему");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-[#F5F6F9] text-black">
      <header className="flex min-h-[64px] flex-wrap items-center justify-between gap-x-4 gap-y-1 bg-white px-4 py-3 sm:min-h-[90px] sm:px-8">
        <span className="text-lg font-bold sm:text-xl">Кредитное решение</span>
        <span className="text-[13px] text-[#4A4A4A]">
          Внутренний сервис банка
        </span>
      </header>

      <main className="flex flex-1 items-start justify-center p-4 sm:items-center sm:p-8">
        <form
          className="w-full max-w-[528px] rounded-2xl bg-white p-5 sm:p-[31px]"
          onSubmit={handleSubmit}
        >
          <h1 className="text-2xl font-bold sm:text-[26px]">Вход в систему</h1>
          <p className="mt-4 text-sm text-[#4A4A4A]">
            Используйте корпоративные учетные данные
          </p>

          <div className="mt-6">
            <label
              htmlFor="login"
              className="mb-2 block text-sm font-semibold text-[#4A4A4A]"
            >
              Логин
            </label>
            <input
              id="login"
              name="login"
              type="text"
              autoComplete="username"
              placeholder="ivan.ivanov"
              className="h-[51px] w-full rounded-md border border-[#B2B2B2] bg-white px-[17px] text-base sm:text-sm text-black outline-none placeholder:text-[#B2B2B2] focus:border-[#277AFF]"
            />
          </div>

          <div className="mt-6">
            <label
              htmlFor="password"
              className="mb-2 block text-sm font-semibold text-[#4A4A4A]"
            >
              Пароль
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              placeholder="**********"
              className="h-[51px] w-full rounded-md border border-[#B2B2B2] bg-white px-[17px] text-base sm:text-sm text-black outline-none placeholder:text-[#B2B2B2] focus:border-[#277AFF]"
            />
          </div>

          {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="mt-7 h-[50px] w-full rounded-md sm:w-auto bg-[#277AFF] px-5 text-base font-bold text-white hover:bg-[#1f68db] disabled:opacity-60"
          >
            {loading ? "Вход..." : "Войти"}
          </button>
        </form>
      </main>
    </div>
  );
}
