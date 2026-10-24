"use client";

import { useEffect, useRef, useState } from "react";

import { refreshSession } from "@/lib/api/client";

export type StreamState = "connecting" | "open" | "reconnecting" | "closed";

export interface StreamEvent<T> {
  id: string;
  data: T;
}

interface Options<T> {
  /** Called with buffered events at most every `flushMs` (the render budget). */
  onEvents: (events: StreamEvent<T>[]) => void;
  /** Start id for the first connection ("$" = new entries only, "0-0" = backlog). */
  since?: string;
  flushMs?: number;
  enabled?: boolean;
}

/** Wait before reconnecting after the browser gave up (ms); doubles up to the cap. */
const BACKOFF = [1000, 2000, 4000, 8000];

/**
 * An SSE subscription to /api/v1/stream/<name>. Events are buffered and handed
 * over at most every `flushMs` (250 ms: at most 4 renders per second). The
 * browser resumes from Last-Event-ID by itself after a network drop. When it
 * gives up (the session expired, the API restarted), the hook refreshes the
 * session and reconnects from the last id it saw, so nothing is lost or repeated.
 */
export function useEventStream<T>(
  path: string,
  event: string,
  { onEvents, since = "$", flushMs = 250, enabled = true }: Options<T>,
): StreamState {
  const [state, setState] = useState<StreamState>("connecting");
  const handler = useRef(onEvents);
  useEffect(() => {
    handler.current = onEvents;
  }, [onEvents]);

  useEffect(() => {
    if (!enabled) return;
    let source: EventSource | null = null;
    let lastId = since;
    let attempt = 0;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let stopped = false;
    const buffer: StreamEvent<T>[] = [];

    const flush = setInterval(() => {
      if (buffer.length) handler.current(buffer.splice(0, buffer.length));
    }, flushMs);

    const open = () => {
      if (stopped) return;
      const sep = path.includes("?") ? "&" : "?";
      source = new EventSource(`${path}${sep}since=${encodeURIComponent(lastId)}`);
      source.onopen = () => {
        attempt = 0;
        setState("open");
      };
      source.addEventListener(event, (e) => {
        const msg = e as MessageEvent<string>;
        lastId = msg.lastEventId || lastId;
        try {
          buffer.push({ id: msg.lastEventId, data: JSON.parse(msg.data) as T });
        } catch {
          // A malformed entry is skipped; the stream continues.
        }
      });
      source.onerror = () => {
        if (source?.readyState === EventSource.CONNECTING) {
          setState("reconnecting"); // the browser retries with Last-Event-ID
          return;
        }
        source?.close();
        setState("reconnecting");
        const wait = BACKOFF[Math.min(attempt, BACKOFF.length - 1)];
        attempt += 1;
        retryTimer = setTimeout(() => {
          void refreshSession().finally(open);
        }, wait);
      };
    };

    open();
    return () => {
      stopped = true;
      clearInterval(flush);
      if (retryTimer) clearTimeout(retryTimer);
      source?.close();
      setState("closed");
    };
  }, [path, event, since, flushMs, enabled]);

  return state;
}
