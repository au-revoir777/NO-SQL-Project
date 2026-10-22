/**
 * Client-side validation (zod), mirroring the server's pydantic models in
 * src/fraudsim/api/v1/schemas/auth.py. The server validates again.
 */
import { z } from "zod";

export const MIN_PASSWORD_LENGTH = 12;

export const loginSchema = z.object({
  email: z.email({ message: "Enter a valid email address" }).max(320),
  password: z.string().min(1, { message: "Enter your password" }).max(1024),
});
export type LoginValues = z.infer<typeof loginSchema>;

export const createUserSchema = z.object({
  email: z.email({ message: "Enter a valid email address" }).max(320),
  display_name: z.string().max(200),
  role: z.enum(["analyst", "admin"]),
  password: z
    .string()
    .min(MIN_PASSWORD_LENGTH, {
      message: `Use at least ${MIN_PASSWORD_LENGTH} characters`,
    })
    .max(1024),
});
export type CreateUserValues = z.infer<typeof createUserSchema>;

/** Only same-site paths are accepted as ?next= targets (no open redirects). */
export function safeNext(next: string | null | undefined): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return "/";
  if (next.startsWith("/login")) return "/";
  return next;
}
