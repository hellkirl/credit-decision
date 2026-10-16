import { redirect } from "react-router";

import type { components } from "./schema";

const STORAGE_KEY = "auth";

type StoredToken = { token: string; expiresAt: number };

export type LoginResponse = components["schemas"]["TokenResponse"];

function read(): StoredToken | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as StoredToken) : null;
  } catch {
    return null;
  }
}

export function getToken(): string | null {
  const stored = read();
  if (!stored) return null;
  if (Date.now() >= stored.expiresAt) {
    clearToken();
    return null;
  }
  return stored.token;
}

export function setToken({ access_token, expires_in }: LoginResponse) {
  const value: StoredToken = { token: access_token, expiresAt: Date.now() + expires_in * 1000 };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
}

export function clearToken() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {}
}

// Login URL that brings the user back to `url` after signing in.
export function loginRedirect(url?: string | URL) {
  if (!url) return redirect("/login");
  const { pathname, search } = new URL(url, window.location.origin);
  return redirect(`/login?${new URLSearchParams({ redirect: pathname + search })}`);
}

// Throws a redirect to /login when there is no valid token.
export function requireToken(request: Request): string {
  const token = getToken();
  if (!token) throw loginRedirect(request.url);
  return token;
}

// Only allow same-origin relative paths as post-login targets.
export function safeRedirect(target: string | null, fallback = "/applications") {
  return target && target.startsWith("/") && !target.startsWith("//") ? target : fallback;
}
