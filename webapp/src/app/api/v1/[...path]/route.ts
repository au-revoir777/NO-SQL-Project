/**
 * Backend-for-frontend proxy: every /api/v1/* request from the browser is
 * forwarded to FastAPI with its cookies, CSRF header and request id, and the
 * response (including every Set-Cookie) is passed back. The browser only ever
 * talks to this origin, so the session cookies stay first-party and httpOnly.
 */
import type { NextRequest } from "next/server";

import { apiBaseUrl } from "@/lib/server/api-base";

export const dynamic = "force-dynamic";

const FORWARD_REQUEST_HEADERS = [
  "accept",
  "content-type",
  "cookie",
  "x-csrf-token",
  "x-request-id",
  "user-agent",
];
const DROP_RESPONSE_HEADERS = new Set([
  "connection",
  "content-encoding",
  "content-length",
  "keep-alive",
  "transfer-encoding",
  "set-cookie",
]);

async function proxy(request: NextRequest, path: string[]): Promise<Response> {
  const url = new URL(`/api/v1/${path.map(encodeURIComponent).join("/")}`, apiBaseUrl());
  url.search = request.nextUrl.search;

  const headers = new Headers();
  for (const name of FORWARD_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const forwardedFor = request.headers.get("x-forwarded-for");
  if (forwardedFor) headers.set("x-forwarded-for", forwardedFor);

  const hasBody = !["GET", "HEAD"].includes(request.method);
  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method: request.method,
      headers,
      body: hasBody ? await request.arrayBuffer() : undefined,
      redirect: "manual",
      cache: "no-store",
    });
  } catch {
    const requestId =
      request.headers.get("x-request-id") ?? crypto.randomUUID().replaceAll("-", "");
    return Response.json(
      {
        error: {
          code: "api_unreachable",
          message: "The FastAPI backend is not reachable from the web app.",
          request_id: requestId,
        },
      },
      { status: 502, headers: { "x-request-id": requestId } },
    );
  }

  const out = new Headers();
  upstream.headers.forEach((value, name) => {
    if (!DROP_RESPONSE_HEADERS.has(name.toLowerCase())) out.set(name, value);
  });
  for (const cookie of upstream.headers.getSetCookie()) out.append("set-cookie", cookie);
  return new Response(upstream.status === 204 ? null : upstream.body, {
    status: upstream.status,
    headers: out,
  });
}

type Ctx = { params: Promise<{ path: string[] }> };

async function handle(request: NextRequest, ctx: Ctx) {
  return proxy(request, (await ctx.params).path);
}

export { handle as DELETE, handle as GET, handle as PATCH, handle as POST, handle as PUT };
