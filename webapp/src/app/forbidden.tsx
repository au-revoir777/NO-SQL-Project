import { ShieldX } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

/** Rendered with HTTP 403 when a page calls forbidden() (e.g. an analyst opening an admin URL). */
export default function Forbidden() {
  return (
    <main className="flex min-h-svh items-center justify-center p-6">
      <div className="flex max-w-md flex-col items-center gap-4 text-center">
        <ShieldX className="text-risk-alert size-10" aria-hidden />
        <h1 className="text-2xl font-semibold">403: Access denied</h1>
        <p className="text-muted-foreground">
          This page needs the admin role. If you need access, ask an administrator to change your
          role.
        </p>
        <Button asChild>
          <Link href="/">Back to the dashboard</Link>
        </Button>
      </div>
    </main>
  );
}
