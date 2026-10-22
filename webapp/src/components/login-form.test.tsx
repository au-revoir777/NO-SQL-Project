import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LoginForm } from "@/components/login-form";
import { jsonResponse, renderWithProviders } from "@/test/render";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, refresh: vi.fn() }) }));

function route(fetchMock: ReturnType<typeof vi.fn>, handlers: Record<string, () => Response>) {
  fetchMock.mockImplementation((input: Request | URL | string) => {
    const url = new URL(input instanceof Request ? input.url : String(input));
    const handler = handlers[url.pathname];
    return Promise.resolve(handler ? handler() : jsonResponse({}, 404));
  });
}

describe("LoginForm", () => {
  beforeEach(() => {
    replace.mockReset();
    document.cookie = "fraudsim_csrf=test-csrf; path=/";
  });

  it("validates the fields before calling the API", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch") as unknown as ReturnType<typeof vi.fn>;
    route(fetchMock, { "/api/v1/auth/refresh": () => jsonResponse({}, 401) });
    renderWithProviders(<LoginForm next="/" />);
    await userEvent.type(screen.getByLabelText("Email"), "not-an-email");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Enter a valid email address")).toBeInTheDocument();
    expect(screen.getByText("Enter your password")).toBeInTheDocument();
    const calls = fetchMock.mock.calls.map((c) =>
      String(c[0] instanceof Request ? c[0].url : c[0]),
    );
    expect(calls.some((u) => u.endsWith("/api/v1/auth/login"))).toBe(false);
  });

  it("sends the CSRF header and goes to the requested page on success", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch") as unknown as ReturnType<typeof vi.fn>;
    route(fetchMock, {
      "/api/v1/auth/refresh": () => jsonResponse({}, 401),
      "/api/v1/auth/login": () =>
        jsonResponse({
          user: {
            id: 1,
            email: "a@example.test",
            display_name: "A",
            role: "analyst",
            is_active: true,
            created_at: "2026-10-22T00:00:00Z",
          },
          access_expires_in_s: 900,
        }),
    });
    renderWithProviders(<LoginForm next="/cases" />);
    await userEvent.type(screen.getByLabelText("Email"), "a@example.test");
    await userEvent.type(screen.getByLabelText("Password"), "any-password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/cases"));
    const login = fetchMock.mock.calls
      .map((c) => c[0] as Request)
      .find((r) => r instanceof Request && r.url.endsWith("/api/v1/auth/login"));
    expect(login?.headers.get("x-csrf-token")).toBe("test-csrf");
  });

  it("explains a lockout with the wait time from Retry-After", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch") as unknown as ReturnType<typeof vi.fn>;
    route(fetchMock, {
      "/api/v1/auth/refresh": () => jsonResponse({}, 401),
      "/api/v1/auth/login": () =>
        jsonResponse(
          { error: { code: "rate_limited", message: "Too many", request_id: "req-9" } },
          429,
          { "retry-after": "600" },
        ),
    });
    renderWithProviders(<LoginForm next="/" />);
    await userEvent.type(screen.getByLabelText("Email"), "a@example.test");
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(
      await screen.findByText("Too many failed attempts. Try again in 10 minutes."),
    ).toBeInTheDocument();
    expect(screen.getByText("Request id: req-9")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
