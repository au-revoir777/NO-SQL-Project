"use client";

import { LogOut, ShieldCheck, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { useSessionUser } from "@/components/session-provider";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { api } from "@/lib/api/client";

function initials(name: string): string {
  const parts = name
    .trim()
    .split(/[\s._-]+/)
    .filter(Boolean);
  return (parts[0]?.[0] ?? "?").toUpperCase() + (parts[1]?.[0] ?? "").toUpperCase();
}

export function UserMenu() {
  const user = useSessionUser();
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function logout() {
    setBusy(true);
    const { response } = await api.POST("/api/v1/auth/logout");
    setBusy(false);
    if (response.status !== 204 && response.status !== 401) {
      toast.error("Sign-out failed. Please try again.");
      return;
    }
    router.replace("/login");
    router.refresh();
  }

  const RoleIcon = user.role === "admin" ? ShieldCheck : UserRound;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="h-9 gap-2 px-2" aria-label={`Account: ${user.email}`}>
          <Avatar className="size-7">
            <AvatarFallback className="text-xs">
              {initials(user.display_name || user.email)}
            </AvatarFallback>
          </Avatar>
          <span className="hidden max-w-40 truncate text-sm md:inline">{user.display_name}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel className="flex flex-col gap-1">
          <span className="truncate font-medium">{user.display_name}</span>
          <span className="text-muted-foreground truncate font-mono text-xs">{user.email}</span>
          <Badge variant="outline" className="mt-1 w-fit capitalize">
            <RoleIcon aria-hidden />
            {user.role}
          </Badge>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => void logout()} disabled={busy}>
          <LogOut aria-hidden />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
