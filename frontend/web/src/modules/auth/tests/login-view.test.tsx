import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { loginMock, routerMock } = vi.hoisted(() => ({
  loginMock: vi.fn(),
  routerMock: {
    replace: vi.fn(),
    refresh: vi.fn(),
  },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("../api/auth-api", () => ({
  authErrorMessage: (_error: unknown, fallback: string) => fallback,
  googleAuthorizationUrl: (returnTo: string) =>
    `/api/v1/auth/google/start?returnTo=${encodeURIComponent(returnTo)}`,
  login: (...args: unknown[]) => loginMock(...args),
}));

import { LoginView } from "../views/login-view";

describe("login", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows validation feedback without submitting", () => {
    render(<LoginView />);

    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(screen.getByLabelText("Email address")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(screen.getByLabelText("Password")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(loginMock).not.toHaveBeenCalled();
    expect(routerMock.replace).not.toHaveBeenCalled();
  });

  it("submits valid credentials and redirects to the safe return target", async () => {
    loginMock.mockResolvedValueOnce(undefined);

    render(<LoginView />);

    fireEvent.change(screen.getByLabelText("Email address"), {
      target: { value: "alex@example.test" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "a-long-test-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() =>
      expect(loginMock).toHaveBeenCalledWith({
        email: "alex@example.test",
        password: "a-long-test-password",
      }),
    );
    expect(routerMock.replace).toHaveBeenCalledWith("/dashboard");
    expect(routerMock.refresh).toHaveBeenCalled();
  });
});
