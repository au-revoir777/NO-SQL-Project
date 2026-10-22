import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppSidebar } from "@/components/app-sidebar";
import { SidebarProvider } from "@/components/ui/sidebar";
import { NAV } from "@/lib/nav";
import { renderWithProviders } from "@/test/render";

vi.mock("next/navigation", () => ({ usePathname: () => "/alerts" }));

describe("AppSidebar", () => {
  it("renders every navigation group and page from the design spec", () => {
    renderWithProviders(
      <SidebarProvider>
        <AppSidebar />
      </SidebarProvider>,
    );
    for (const label of ["Monitor", "Investigate", "Simulate", "Research", "Admin"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    const total = NAV.reduce((n, g) => n + g.items.length, 0);
    const nav = screen.getByRole("navigation", { name: "Main navigation" });
    expect(within(nav).getAllByRole("link").length).toBeGreaterThanOrEqual(total);
  });

  it("marks the current page and labels unbuilt pages with their milestone", () => {
    renderWithProviders(
      <SidebarProvider>
        <AppSidebar />
      </SidebarProvider>,
    );
    const alerts = screen.getByRole("link", { name: "Alerts" });
    expect(alerts).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Dashboard" })).not.toHaveAttribute("aria-current");
    // Alerts, Cases and Audit all arrive in P5.
    expect(screen.getAllByTitle("Arrives in milestone P5")).toHaveLength(3);
  });
});
