import {
  Activity,
  BellRing,
  BookOpenCheck,
  Briefcase,
  FileText,
  FlaskConical,
  History,
  LayoutDashboard,
  type LucideIcon,
  PlayCircle,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Users,
} from "lucide-react";

export interface NavItem {
  title: string;
  href: string;
  icon: LucideIcon;
  /** Milestone that implements the page (phase2_prompt.md); undefined = available now. */
  milestone?: string;
  adminOnly?: boolean;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV: NavGroup[] = [
  {
    label: "Monitor",
    items: [
      { title: "Dashboard", href: "/", icon: LayoutDashboard },
      { title: "Alerts", href: "/alerts", icon: BellRing },
      { title: "Cases", href: "/cases", icon: Briefcase },
    ],
  },
  {
    label: "Investigate",
    items: [
      { title: "Explorer", href: "/explorer", icon: Search, milestone: "P6" },
      { title: "Reports", href: "/reports", icon: FileText, milestone: "P7" },
    ],
  },
  {
    label: "Simulate",
    items: [
      { title: "Simulator", href: "/simulator", icon: PlayCircle },
      { title: "Replays", href: "/replays", icon: History },
    ],
  },
  {
    label: "Research",
    items: [{ title: "Experiments", href: "/experiments", icon: FlaskConical, milestone: "P8" }],
  },
  {
    label: "Admin",
    items: [
      { title: "Rules", href: "/rules", icon: SlidersHorizontal, milestone: "P9", adminOnly: true },
      { title: "Users", href: "/users", icon: Users, adminOnly: true },
      { title: "Audit", href: "/audit", icon: ShieldCheck, adminOnly: true },
    ],
  },
];

export const ALL_ITEMS: NavItem[] = NAV.flatMap((g) => g.items);

/** The navigation a role may see: admin-only items (and empty groups) removed for analysts. */
export function navFor(role: "analyst" | "admin"): NavGroup[] {
  return NAV.map((g) => ({
    ...g,
    items: g.items.filter((i) => role === "admin" || !i.adminOnly),
  })).filter((g) => g.items.length > 0);
}

export function findNav(pathname: string): { group: NavGroup; item: NavItem } | undefined {
  for (const group of NAV) {
    for (const item of group.items) {
      if (item.href === "/" ? pathname === "/" : pathname.startsWith(item.href)) {
        return { group, item };
      }
    }
  }
  return undefined;
}

export const APP_ICON = Activity;
export const DOCS_ICON = BookOpenCheck;
