// REST + WebSocket client. In development Vite proxies /api and /ws to :8000;
// in production the dashboard is served by FastAPI itself (same origin, at /ui).
// Every route needs a session (cookie set by /api/v1/auth/login); POSTs also send
// the CSRF token, and a 401 triggers one silent refresh before giving up.

export const API_BASE = import.meta.env.DEV ? '/api' : '';

/** Raised when the session is gone; the AuthGate shows the sign-in form. */
export class SignedOut extends Error {}

let onSignedOut: () => void = () => undefined;
export function setSignedOutHandler(fn: () => void): void {
  onSignedOut = fn;
}

function readCookie(name: string): string {
  const hit = document.cookie.split('; ').find((c) => c.startsWith(`${name}=`));
  return hit ? decodeURIComponent(hit.slice(name.length + 1)) : '';
}

async function csrfToken(): Promise<string> {
  const have = readCookie('fraudsim_csrf');
  if (have) return have;
  const r = await fetch(`${API_BASE}/api/v1/auth/csrf`);
  return ((await r.json()) as { csrf_token: string }).csrf_token;
}

export async function refreshSession(): Promise<boolean> {
  const r = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
    method: 'POST',
    headers: { 'X-CSRF-Token': await csrfToken() },
  });
  return r.ok;
}

async function send(path: string, init: RequestInit = {}): Promise<Response> {
  const go = async () => {
    const headers = new Headers(init.headers);
    if (init.method && init.method !== 'GET') headers.set('X-CSRF-Token', await csrfToken());
    return fetch(`${API_BASE}${path}`, { ...init, headers });
  };
  let r = await go();
  if (r.status === 401 && (await refreshSession())) r = await go();
  if (r.status === 401) {
    onSignedOut();
    throw new SignedOut(`${path}: session ended`);
  }
  return r;
}

export async function getJSON<T>(path: string): Promise<T> {
  const r = await send(path);
  if (!r.ok) throw new Error(`${path}: ${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}

export async function postJSON<T>(path: string, body: unknown = {}): Promise<T> {
  const r = await send(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${path}: ${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}

export interface SessionUser {
  email: string;
  display_name: string | null;
  role: 'analyst' | 'admin';
}

/** Current user, after one silent refresh; null when signed out. */
export async function currentUser(): Promise<SessionUser | null> {
  const me = () => fetch(`${API_BASE}/api/v1/auth/me`);
  let r = await me();
  if (r.status === 401 && (await refreshSession())) r = await me();
  if (!r.ok) return null;
  return ((await r.json()) as { user: SessionUser }).user;
}

export async function login(email: string, password: string): Promise<string | null> {
  const r = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': await csrfToken() },
    body: JSON.stringify({ email, password }),
  });
  if (r.ok) return null;
  if (r.status === 429) return 'Too many failed attempts. Try again later.';
  if (r.status === 401) return 'Email or password is incorrect.';
  return `Sign-in failed (${r.status}).`;
}

export async function logout(): Promise<void> {
  await fetch(`${API_BASE}/api/v1/auth/logout`, {
    method: 'POST',
    headers: { 'X-CSRF-Token': await csrfToken() },
  });
}

export function wsUrl(): string {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${location.host}/ws`;
}

/** Reconnecting WebSocket; calls onMessage for every parsed JSON message. */
export function connectWs(onMessage: (msg: any) => void, onState: (open: boolean) => void): () => void {
  let ws: WebSocket | null = null;
  let closed = false;
  let retry: number | undefined;
  const open = () => {
    ws = new WebSocket(wsUrl());
    ws.onopen = () => onState(true);
    ws.onmessage = (e) => {
      try {
        onMessage(JSON.parse(e.data));
      } catch {
        /* ignore malformed */
      }
    };
    ws.onclose = (e) => {
      onState(false);
      if (closed) return;
      if (e.code === 4401) {
        // Session expired or revoked: refresh it, or hand over to the sign-in form.
        void refreshSession().then((ok) => (ok ? open() : onSignedOut()));
        return;
      }
      retry = window.setTimeout(open, 1500);
    };
  };
  open();
  return () => {
    closed = true;
    if (retry) window.clearTimeout(retry);
    ws?.close();
  };
}

export const fmt = (x: number | null | undefined, d = 2): string =>
  x === null || x === undefined || Number.isNaN(x) ? '–' : Number(x).toFixed(d);

export const pct = (x: number | null | undefined): string =>
  x === null || x === undefined ? '–' : `${Math.round(x * 100)}%`;

export const FEATURE_LABELS: Record<string, string> = {
  size: 'ring size',
  density: 'pairs directly linked',
  share_device: 'share one device',
  share_card: 'share one card',
  share_ip: 'share one IP',
  hub_adjusted_weight: 'hub-adjusted sharing weight',
  cycle_present: 'money returns to origin',
  cycle_length: 'cycle length',
  temporal_burstiness: 'linked within a short burst',
  account_age_similarity: 'similar account ages',
  account_age_min: 'age of oldest account',
  internal_txns_per_member: 'transfers between members',
  amount_mean_log: 'typical transfer size',
  amount_cv: 'variation of amounts',
  near_threshold_frac: 'just under 10k threshold',
  growth_rate: 'members added per minute',
  risk_signal_fraction: 'also in another flagged group',
  hub_exposure: 'busiest shared attribute',
  n_detectors: 'detectors agreeing',
};
