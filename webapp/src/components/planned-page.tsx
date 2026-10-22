import { EmptyState } from "@/components/empty-state";
import { ALL_ITEMS } from "@/lib/nav";

/** Placeholder for a page whose milestone has not been built yet. No sample data. */
export function PlannedPage({ href }: { href: string }) {
  const item = ALL_ITEMS.find((i) => i.href === href);
  if (!item) throw new Error(`unknown page ${href}`);
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">{item.title}</h1>
      <EmptyState icon={item.icon} title={`${item.title} is not built yet`}>
        This page arrives in milestone {item.milestone} of the web app plan. It will show data from
        the detection engine only; nothing here is sample data.
      </EmptyState>
    </div>
  );
}
