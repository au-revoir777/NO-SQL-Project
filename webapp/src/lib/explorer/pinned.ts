"use client";

import { useSyncExternalStore } from "react";

/**
 * The entity pinned for comparison ("kind:id" plus its source), kept per tab in
 * sessionStorage. Storage can be unavailable (private mode, tests): then the pin
 * lives in memory for this page only.
 */
const KEY = "fraudsim.explorer.pin";
let memory: string | null = null;
const listeners = new Set<() => void>();

function read(): string | null {
  try {
    return window.sessionStorage.getItem(KEY);
  } catch {
    return memory;
  }
}

export function setPinned(value: string | null) {
  memory = value;
  try {
    if (value === null) window.sessionStorage.removeItem(KEY);
    else window.sessionStorage.setItem(KEY, value);
  } catch {
    // memory only
  }
  listeners.forEach((l) => l());
}

export function usePinned(): string | null {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    read,
    () => null,
  );
}
