import type { Metadata } from "next";

import { UsersAdmin } from "@/components/users-admin";

export const metadata: Metadata = { title: "Users" };

export default function UsersPage() {
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Users</h1>
        <p className="text-muted-foreground">
          Create accounts, change roles and deactivate access. Accounts are never deleted; every
          change is written to the audit trail.
        </p>
      </div>
      <UsersAdmin />
    </div>
  );
}
