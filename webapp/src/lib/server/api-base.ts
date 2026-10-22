/**
 * Where the Next.js server reaches FastAPI. Server-side only: imported by route
 * handlers and server components, never by client components.
 */
export function apiBaseUrl(): string {
  return process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
}
