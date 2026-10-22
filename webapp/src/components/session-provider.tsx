"use client";

import { createContext, type ReactNode, useContext } from "react";

import type { UserOut } from "@/lib/api/client";

const SessionContext = createContext<UserOut | null>(null);

/** The signed-in user, resolved on the server by the app layout. */
export function SessionProvider({ user, children }: { user: UserOut; children: ReactNode }) {
  return <SessionContext.Provider value={user}>{children}</SessionContext.Provider>;
}

export function useSessionUser(): UserOut {
  const user = useContext(SessionContext);
  if (!user) throw new Error("useSessionUser must be used inside <SessionProvider>");
  return user;
}

/** Optional variant for components that may render outside the app shell. */
export function useOptionalSessionUser(): UserOut | null {
  return useContext(SessionContext);
}
