"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar";
import { APP_ICON, findNav, NAV } from "@/lib/nav";

export function AppSidebar() {
  const pathname = usePathname() ?? "/";
  const active = findNav(pathname)?.item.href;
  const AppIcon = APP_ICON;

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild tooltip="FraudSim">
              <Link href="/">
                <span className="bg-primary text-primary-foreground flex size-8 items-center justify-center rounded-lg">
                  <AppIcon className="size-4" aria-hidden />
                </span>
                <span className="flex flex-col leading-tight">
                  <span className="font-semibold">FraudSim</span>
                  <span className="text-muted-foreground text-xs">Fraud-ring investigation</span>
                </span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <nav aria-label="Main navigation">
          {NAV.map((group) => (
            <SidebarGroup key={group.label}>
              <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
              <SidebarMenu>
                {group.items.map((item) => (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton asChild isActive={active === item.href} tooltip={item.title}>
                      <Link
                        href={item.href}
                        aria-current={active === item.href ? "page" : undefined}
                      >
                        <item.icon aria-hidden />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                    {item.milestone ? (
                      <SidebarMenuBadge
                        className="text-muted-foreground font-mono text-[11px]"
                        title={`Arrives in milestone ${item.milestone}`}
                      >
                        {item.milestone}
                      </SidebarMenuBadge>
                    ) : null}
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroup>
          ))}
        </nav>
      </SidebarContent>
      <SidebarFooter>
        <p className="text-muted-foreground px-2 text-xs group-data-[collapsible=icon]:hidden">
          Simulated data for research and demo use.
        </p>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
