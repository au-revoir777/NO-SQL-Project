import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

export type HealthV1 = components["schemas"]["HealthV1"];
export type ComponentHealth = components["schemas"]["ComponentHealth"];
export type ErrorEnvelope = components["schemas"]["ErrorEnvelope"];
export type UserOut = components["schemas"]["UserOut"];

const CSRF_COOKIE = "fraudsim_csrf";
const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const NO_REFRESH = ["/api/v1/auth/login", "/api/v1/auth/refresh", "/api/v1/auth/csrf"];

function origin(): string {
  // Same origin: the Next.js route handler forwards /api/v1 to FastAPI. An
  // absolute base URL is needed outside the browser (tests).
  return typeof window === "undefined" ? "http://localhost" : window.location.origin;
}

export function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const hit = document.cookie.split("; ").find((c) => c.startsWith(`${name}=`));
  return hit ? decodeURIComponent(hit.slice(name.length + 1)) : null;
}

/** The CSRF token (double-submit cookie), fetched once if not set yet. */
export async function csrfToken(): Promise<string> {
  const existing = readCookie(CSRF_COOKIE);
  if (existing) return existing;
  const res = await globalThis.fetch(new URL("/api/v1/auth/csrf", origin()), {
    credentials: "same-origin",
  });
  const body = (await res.json()) as { csrf_token: string };
  return readCookie(CSRF_COOKIE) ?? body.csrf_token;
}

async function withCsrf(request: Request): Promise<Request> {
  if (!UNSAFE.has(request.method) || request.headers.has("x-csrf-token")) return request;
  const headers = new Headers(request.headers);
  headers.set("x-csrf-token", await csrfToken());
  return new Request(request, { headers });
}

let refreshing: Promise<boolean> | null = null;

/** One refresh at a time; true if a new access token was issued. */
export function refreshSession(): Promise<boolean> {
  refreshing ??= (async () => {
    try {
      const res = await globalThis.fetch(new URL("/api/v1/auth/refresh", origin()), {
        method: "POST",
        headers: { "x-csrf-token": await csrfToken() },
        credentials: "same-origin",
      });
      return res.ok;
    } catch {
      return false;
    } finally {
      setTimeout(() => (refreshing = null), 0);
    }
  })();
  return refreshing;
}

/** fetch with CSRF for unsafe methods and one transparent refresh on an expired session. */
export async function apiFetch(input: Request): Promise<Response> {
  const request = await withCsrf(input);
  const retry = request.clone();
  const response = await globalThis.fetch(request);
  const path = new URL(request.url).pathname;
  if (response.status !== 401 || NO_REFRESH.includes(path)) return response;
  if (!(await refreshSession())) return response;
  return globalThis.fetch(retry);
}

/** Typed client for /api/v1 (types generated from docs/api/openapi.json). */
export const api = createClient<paths>({ baseUrl: origin(), fetch: apiFetch });

/** An /api/v1 error with the server's code and request id, for display and support. */
export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly requestId: string | null,
    readonly retryAfter: number | null = null,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export function toApiError(error: unknown, response: Response): ApiRequestError {
  const env = error as Partial<ErrorEnvelope> | undefined;
  const requestId = env?.error?.request_id ?? response.headers.get("x-request-id");
  const retryAfter = Number(response.headers.get("retry-after")) || null;
  return new ApiRequestError(
    env?.error?.message ?? `Request failed with status ${response.status}`,
    response.status,
    env?.error?.code ?? "http_error",
    requestId,
    retryAfter,
  );
}
