import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppSidebar } from "@/components/app-sidebar";
import { SessionProvider } from "@/components/session-provider";
import { SidebarProvider } from "@/components/ui/sidebar";
import type { UserOut } from "@/lib/api/client";
import { NAV } from "@/lib/nav";
import { renderWithProviders } from "@/test/render";

vi.mock("next/navigation", () => ({ usePathname: () => "/alerts" }));

// Test fixtures shaped like GET /api/v1/auth/me's user (not real accounts).
const ADMIN: UserOut = {
  id: 1,
  email: "admin@example.test",
  display_name: "Admin",
  role: "admin",
  is_active: true,
  created_at: "2026-10-22T00:00:00Z",
  last_login_at: null,
};
const ANALYST: UserOut = { ...ADMIN, id: 2, email: "analyst@example.test", role: "analyst" };

function renderAs(user: UserOut) {
  return renderWithProviders(
    <SessionProvider user={user}>
      <SidebarProvider>
        <AppSidebar />
      </SidebarProvider>
    </SessionProvider>,
  );
}

describe("AppSidebar", () => {
  it("shows every navigation group and page to an admin", () => {
    renderAs(ADMIN);
    for (const label of ["Monitor", "Investigate", "Simulate", "Research", "Admin"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    const total = NAV.reduce((n, g) => n + g.items.length, 0);
    const nav = screen.getByRole("navigation", { name: "Main navigation" });
    expect(within(nav).getAllByRole("link").length).toBe(total);
    expect(screen.getByRole("link", { name: "Users" })).toBeInTheDocument();
  });

  it("hides the admin pages from an analyst", () => {
    renderAs(ANALYST);
    expect(screen.queryByText("Admin")).not.toBeInTheDocument();
    for (const name of ["Rules", "Users", "Audit"]) {
      expect(screen.queryByRole("link", { name })).not.toBeInTheDocument();
    }
    expect(screen.getByRole("link", { name: "Alerts" })).toBeInTheDocument();
  });

  it("marks the current page and labels unbuilt pages with their milestone", () => {
    renderAs(ADMIN);
    const alerts = screen.getByRole("link", { name: "Alerts" });
    expect(alerts).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Dashboard" })).not.toHaveAttribute("aria-current");
    // Alerts, Cases and Audit all arrive in P5.
    expect(screen.getAllByTitle("Arrives in milestone P5")).toHaveLength(3);
  });
});
