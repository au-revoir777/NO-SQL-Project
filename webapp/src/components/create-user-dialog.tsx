"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { LoaderCircle, UserPlus } from "lucide-react";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ApiRequestError } from "@/lib/api/client";
import { useCreateUser } from "@/lib/api/queries";
import { type CreateUserValues, createUserSchema, MIN_PASSWORD_LENGTH } from "@/lib/schemas";

export function CreateUserDialog() {
  const [open, setOpen] = useState(false);
  const create = useCreateUser();
  const form = useForm<CreateUserValues>({
    resolver: zodResolver(createUserSchema),
    defaultValues: { email: "", display_name: "", role: "analyst", password: "" },
  });
  const { errors, isSubmitting } = form.formState;

  async function onSubmit(values: CreateUserValues) {
    try {
      const user = await create.mutateAsync(values);
      toast.success(`Created ${user.role} ${user.email}`);
      form.reset();
      setOpen(false);
    } catch (e) {
      const message = e instanceof ApiRequestError ? e.message : "Could not create the user.";
      if (e instanceof ApiRequestError && e.status === 409) {
        form.setError("email", { message });
      } else {
        form.setError("root", { message });
      }
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) form.reset();
      }}
    >
      <DialogTrigger asChild>
        <Button>
          <UserPlus aria-hidden />
          New user
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New user</DialogTitle>
          <DialogDescription>
            The user signs in with this email and password. Share the password through a separate
            channel.
          </DialogDescription>
        </DialogHeader>
        <form id="create-user" onSubmit={form.handleSubmit(onSubmit)} noValidate>
          <FieldGroup>
            <Field data-invalid={errors.email ? true : undefined}>
              <FieldLabel htmlFor="new-email">Email</FieldLabel>
              <Input
                id="new-email"
                type="email"
                autoComplete="off"
                aria-invalid={errors.email ? true : undefined}
                {...form.register("email")}
              />
              <FieldError errors={[errors.email]} />
            </Field>
            <Field>
              <FieldLabel htmlFor="new-name">Display name</FieldLabel>
              <Input id="new-name" autoComplete="off" {...form.register("display_name")} />
            </Field>
            <Field>
              <FieldLabel htmlFor="new-role">Role</FieldLabel>
              <Controller
                control={form.control}
                name="role"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="new-role" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="analyst">Analyst</SelectItem>
                      <SelectItem value="admin">Admin</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
            </Field>
            <Field data-invalid={errors.password ? true : undefined}>
              <FieldLabel htmlFor="new-password">Password</FieldLabel>
              <Input
                id="new-password"
                type="password"
                autoComplete="new-password"
                aria-invalid={errors.password ? true : undefined}
                {...form.register("password")}
              />
              <FieldDescription>At least {MIN_PASSWORD_LENGTH} characters.</FieldDescription>
              <FieldError errors={[errors.password]} />
            </Field>
            {errors.root ? <FieldError>{errors.root.message}</FieldError> : null}
          </FieldGroup>
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button type="submit" form="create-user" disabled={isSubmitting}>
            {isSubmitting ? <LoaderCircle className="animate-spin" aria-hidden /> : null}
            Create user
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
