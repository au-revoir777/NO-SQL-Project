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
      { title: "Alerts", href: "/alerts", icon: BellRing, milestone: "P5" },
      { title: "Cases", href: "/cases", icon: Briefcase, milestone: "P5" },
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
      { title: "Simulator", href: "/simulator", icon: PlayCircle, milestone: "P4" },
      { title: "Replays", href: "/replays", icon: History, milestone: "P4" },
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
      { title: "Users", href: "/users", icon: Users, milestone: "P2", adminOnly: true },
      { title: "Audit", href: "/audit", icon: ShieldCheck, milestone: "P5", adminOnly: true },
    ],
  },
];

export const ALL_ITEMS: NavItem[] = NAV.flatMap((g) => g.items);

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
