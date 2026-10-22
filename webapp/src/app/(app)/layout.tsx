import { headers } from "next/headers";
import type { ReactNode } from "react";

import { AppSidebar } from "@/components/app-sidebar";
import { SessionProvider } from "@/components/session-provider";
import { SiteHeader } from "@/components/site-header";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { requireUser } from "@/lib/server/session";

export default async function AppLayout({ children }: { children: ReactNode }) {
  const path = (await headers()).get("x-pathname") ?? "/";
  const user = await requireUser(path);
  return (
    <SessionProvider user={user}>
      <SidebarProvider>
        <a
          href="#main"
          className="bg-background sr-only z-50 rounded-md px-3 py-2 focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
        >
          Skip to content
        </a>
        <AppSidebar />
        <SidebarInset>
          <SiteHeader />
          <main id="main" className="mx-auto w-full max-w-[1440px] flex-1 p-4 md:p-6">
            {children}
          </main>
        </SidebarInset>
      </SidebarProvider>
    </SessionProvider>
  );
}
