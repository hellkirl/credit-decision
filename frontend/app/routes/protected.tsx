import { Outlet, useRouteLoaderData } from "react-router";

import { api, type User } from "~/lib/api";
import { requireToken } from "~/lib/auth";
import type { Route } from "./+types/protected";

// Layout for every page that needs a signed-in user. The token lives only in
// the browser, so the server renders just the fallback below and the pages
// themselves render after this check passes on the client.
export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  requireToken(request);
  try {
    return { user: await api<User>("/auth/me") };
  } catch (error) {
    if (error instanceof Response) throw error;
    return { user: null };
  }
}

export function HydrateFallback() {
  return <div className="min-h-screen bg-[#F5F6F9]" />;
}

export function useCurrentUser(): User | null {
  const data = useRouteLoaderData<typeof clientLoader>("routes/protected");
  return data?.user ?? null;
}

export default function Protected() {
  return <Outlet />;
}
