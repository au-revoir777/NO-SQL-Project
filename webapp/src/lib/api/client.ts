import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

export type HealthV1 = components["schemas"]["HealthV1"];
export type ComponentHealth = components["schemas"]["ComponentHealth"];
export type ErrorEnvelope = components["schemas"]["ErrorEnvelope"];

/** Typed client for /api/v1 (types generated from docs/api/openapi.json). */
export const api = createClient<paths>({
  // Same origin: Next.js forwards /api/v1 to FastAPI. An absolute base URL is
  // needed outside the browser (tests), where relative Request URLs are invalid.
  baseUrl: typeof window === "undefined" ? "" : window.location.origin,
  // Resolve fetch at call time, so tests and instrumentation can replace it.
  fetch: (request: Request) => globalThis.fetch(request),
});

/** An /api/v1 error with the server's code and request id, for display and support. */
export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly requestId: string | null,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export function toApiError(error: unknown, response: Response): ApiRequestError {
  const env = error as Partial<ErrorEnvelope> | undefined;
  const requestId = env?.error?.request_id ?? response.headers.get("x-request-id");
  return new ApiRequestError(
    env?.error?.message ?? `Request failed with status ${response.status}`,
    response.status,
    env?.error?.code ?? "http_error",
    requestId,
  );
}
