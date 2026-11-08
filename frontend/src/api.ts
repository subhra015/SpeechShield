// frontend/src/api.ts
export const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

let csrfToken: string | null = null;

export function setCsrfToken(t: string | null) {
  csrfToken = t;
}

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
  return match ? decodeURIComponent(match[2]) : null;
}

export async function api(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers || {});
  if (!headers.has("Content-Type") && init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  // CSRF for unsafe methods when cookie auth is used.
  if (init.method && !["GET", "HEAD", "OPTIONS"].includes(init.method.toUpperCase())) {
    const t = csrfToken || readCookie("speechshield_csrf");
    if (t) headers.set("X-CSRF-Token", t);
  }
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
  // capture csrf token from cookie after login
  const c = readCookie("speechshield_csrf");
  if (c) csrfToken = c;
  return res;
}
