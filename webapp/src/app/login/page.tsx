import { Activity } from "lucide-react";
import type { Metadata } from "next";

import { LoginForm } from "@/components/login-form";
import { ThemeToggle } from "@/components/theme-toggle";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { safeNext } from "@/lib/schemas";

export const metadata: Metadata = { title: "Sign in" };

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string | string[] }>;
}) {
  const raw = (await searchParams).next;
  const next = safeNext(Array.isArray(raw) ? raw[0] : raw);
  return (
    <main className="bg-muted/40 relative flex min-h-svh items-center justify-center p-4">
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>
      <div className="w-full max-w-sm space-y-6">
        <div className="flex items-center justify-center gap-2">
          <span className="bg-primary text-primary-foreground flex size-9 items-center justify-center rounded-lg">
            <Activity className="size-5" aria-hidden />
          </span>
          <span className="text-lg font-semibold">FraudSim</span>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>
              <h1 className="text-xl">Sign in</h1>
            </CardTitle>
            <CardDescription>
              Fraud-ring investigation on simulated transaction data.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <LoginForm next={next} />
          </CardContent>
        </Card>
        <p className="text-muted-foreground text-center text-xs">
          Accounts are created by an administrator. Generated from simulated data for research and
          demo purposes.
        </p>
      </div>
    </main>
  );
}
