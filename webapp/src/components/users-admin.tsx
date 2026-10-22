"use client";

import {
  CircleCheck,
  CircleSlash,
  RefreshCw,
  ShieldCheck,
  TriangleAlert,
  UserRound,
  Users,
} from "lucide-react";
import { toast } from "sonner";

import { CreateUserDialog } from "@/components/create-user-dialog";
import { EmptyState } from "@/components/empty-state";
import { useSessionUser } from "@/components/session-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ApiRequestError, type UserOut } from "@/lib/api/client";
import { useUpdateUser, useUsers } from "@/lib/api/queries";

const dateFmt = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

function formatDate(iso: string | null | undefined): string {
  return iso ? dateFmt.format(new Date(iso)) : "Never";
}

function errorText(e: unknown): string {
  return e instanceof ApiRequestError ? e.message : "The change could not be saved.";
}

function UserRow({ user, isSelf }: { user: UserOut; isSelf: boolean }) {
  const update = useUpdateUser();

  async function setRole(role: "analyst" | "admin") {
    try {
      await update.mutateAsync({ id: user.id, role });
      toast.success(`${user.email} is now ${role === "admin" ? "an admin" : "an analyst"}.`);
    } catch (e) {
      toast.error(errorText(e));
    }
  }

  async function setActive(is_active: boolean) {
    try {
      await update.mutateAsync({ id: user.id, is_active });
      toast.success(`${user.email} ${is_active ? "reactivated" : "deactivated"}.`);
    } catch (e) {
      toast.error(errorText(e));
    }
  }

  return (
    <TableRow className="h-10">
      <TableCell>
        <div className="flex flex-col">
          <span className="font-medium">
            {user.display_name}
            {isSelf ? <span className="text-muted-foreground"> (you)</span> : null}
          </span>
          <span className="text-muted-foreground font-mono text-xs">{user.email}</span>
        </div>
      </TableCell>
      <TableCell>
        <Select
          value={user.role}
          onValueChange={(v) => void setRole(v as "analyst" | "admin")}
          disabled={isSelf || update.isPending}
        >
          <SelectTrigger className="w-32" aria-label={`Role of ${user.email}`}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="analyst">
              <UserRound aria-hidden /> Analyst
            </SelectItem>
            <SelectItem value="admin">
              <ShieldCheck aria-hidden /> Admin
            </SelectItem>
          </SelectContent>
        </Select>
      </TableCell>
      <TableCell>
        {user.is_active ? (
          <Badge variant="outline" className="text-ok">
            <CircleCheck aria-hidden /> Active
          </Badge>
        ) : (
          <Badge variant="outline" className="text-muted-foreground">
            <CircleSlash aria-hidden /> Deactivated
          </Badge>
        )}
      </TableCell>
      <TableCell className="text-muted-foreground tabular text-right">
        {formatDate(user.last_login_at)}
      </TableCell>
      <TableCell className="text-right">
        {user.is_active ? (
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="outline" size="sm" disabled={isSelf || update.isPending}>
                Deactivate
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Deactivate {user.email}?</AlertDialogTitle>
                <AlertDialogDescription>
                  Their sessions end at once and they can no longer sign in. The account and its
                  history are kept; you can reactivate it later.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={() => void setActive(false)}>
                  Deactivate
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        ) : (
          <Button
            variant="outline"
            size="sm"
            onClick={() => void setActive(true)}
            disabled={update.isPending}
          >
            Reactivate
          </Button>
        )}
      </TableCell>
    </TableRow>
  );
}

export function UsersAdmin() {
  const me = useSessionUser();
  const { data, error, isPending, refetch } = useUsers();

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <CreateUserDialog />
      </div>
      <Card className="overflow-hidden py-0">
        <CardContent className="px-0">
          {isPending ? (
            <div className="space-y-2 p-4" aria-busy="true" aria-label="Loading users">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : error ? (
            <div className="p-4">
              <Alert variant="destructive">
                <TriangleAlert aria-hidden />
                <AlertTitle>Could not load users</AlertTitle>
                <AlertDescription>
                  <p>{error.message}</p>
                  {error instanceof ApiRequestError && error.requestId ? (
                    <p className="font-mono text-xs">Request id: {error.requestId}</p>
                  ) : null}
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-2"
                    onClick={() => void refetch()}
                  >
                    <RefreshCw aria-hidden /> Retry
                  </Button>
                </AlertDescription>
              </Alert>
            </div>
          ) : data.length === 0 ? (
            <div className="p-4">
              <EmptyState icon={Users} title="No users yet">
                Create the first account with New user.
              </EmptyState>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Last sign-in</TableHead>
                  <TableHead className="text-right">
                    <span className="sr-only">Actions</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((u) => (
                  <UserRow key={u.id} user={u} isSelf={u.id === me.id} />
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
