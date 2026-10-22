import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export function EmptyState({
  icon: Icon,
  title,
  children,
  action,
}: {
  icon: LucideIcon;
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed px-6 py-16 text-center">
      <Icon className="text-muted-foreground size-8" aria-hidden />
      <h2 className="text-base font-semibold">{title}</h2>
      <p className="text-muted-foreground max-w-md">{children}</p>
      {action}
    </div>
  );
}
