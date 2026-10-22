"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { LoaderCircle, LogIn, TriangleAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { api, refreshSession, toApiError } from "@/lib/api/client";
import { type LoginValues, loginSchema, safeNext } from "@/lib/schemas";

function describe(code: string, retryAfter: number | null): string {
  if (code === "invalid_credentials") return "Email or password is incorrect.";
  if (code === "rate_limited") {
    const minutes = retryAfter ? Math.ceil(retryAfter / 60) : null;
    return minutes
      ? `Too many failed attempts. Try again in ${minutes} minute${minutes === 1 ? "" : "s"}.`
      : "Too many failed attempts. Try again later.";
  }
  if (code === "api_unreachable")
    return "The server is not reachable. Check that the API is running.";
  return "Sign-in failed. Please try again.";
}

export function LoginForm({ next }: { next: string }) {
  const router = useRouter();
  const [error, setError] = useState<{ message: string; requestId: string | null } | null>(null);
  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });
  const { errors, isSubmitting } = form.formState;

  // A still-valid refresh session signs the user straight back in.
  useEffect(() => {
    let cancelled = false;
    void refreshSession().then((ok) => {
      if (ok && !cancelled) {
        router.replace(safeNext(next));
        router.refresh();
      }
    });
    return () => {
      cancelled = true;
    };
  }, [next, router]);

  async function onSubmit(values: LoginValues) {
    setError(null);
    const { data, error: err, response } = await api.POST("/api/v1/auth/login", { body: values });
    if (data) {
      router.replace(safeNext(next));
      router.refresh();
      return;
    }
    const e = toApiError(err, response);
    setError({ message: describe(e.code, e.retryAfter), requestId: e.requestId });
  }

  return (
    <form onSubmit={form.handleSubmit(onSubmit)} noValidate aria-describedby="login-error">
      <FieldGroup>
        {error ? (
          <Alert variant="destructive" id="login-error">
            <TriangleAlert aria-hidden />
            <AlertTitle>Could not sign in</AlertTitle>
            <AlertDescription>
              <p>{error.message}</p>
              {error.requestId ? (
                <p className="font-mono text-xs">Request id: {error.requestId}</p>
              ) : null}
            </AlertDescription>
          </Alert>
        ) : null}
        <Field data-invalid={errors.email ? true : undefined}>
          <FieldLabel htmlFor="email">Email</FieldLabel>
          <Input
            id="email"
            type="email"
            autoComplete="username"
            autoFocus
            aria-invalid={errors.email ? true : undefined}
            {...form.register("email")}
          />
          <FieldError errors={[errors.email]} />
        </Field>
        <Field data-invalid={errors.password ? true : undefined}>
          <FieldLabel htmlFor="password">Password</FieldLabel>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            aria-invalid={errors.password ? true : undefined}
            {...form.register("password")}
          />
          <FieldError errors={[errors.password]} />
        </Field>
        <Button type="submit" disabled={isSubmitting} className="w-full">
          {isSubmitting ? (
            <LoaderCircle className="animate-spin" aria-hidden />
          ) : (
            <LogIn aria-hidden />
          )}
          Sign in
        </Button>
      </FieldGroup>
    </form>
  );
}
