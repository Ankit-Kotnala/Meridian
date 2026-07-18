import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RegisterView } from "../views/register-view";

function json(body: unknown, init?: ResponseInit) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
    ...init,
  });
}

describe("registration", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows associated client validation without sending a request", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<RegisterView />);

    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(screen.getByLabelText("Name")).toHaveAccessibleDescription(
      "Enter the name you want CareerOS to use.",
    );
    expect(screen.getByLabelText("Email address")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(screen.getByLabelText("Password")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("submits through the CSRF bootstrap and shows enumeration-safe success", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json({ csrfToken: "csrf-token" }))
      .mockResolvedValueOnce(json({ message: "accepted" }, { status: 202 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<RegisterView />);

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Alex Morgan" },
    });
    fireEvent.change(screen.getByLabelText("Email address"), {
      target: { value: "alex@example.test" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "a-long-test-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(
      await screen.findByRole("heading", { name: "Check your email" }),
    ).toBeVisible();
    expect(
      screen.getByText(/same for existing and new accounts/i),
    ).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const request = fetchMock.mock.calls[1]?.[1] as RequestInit;
    expect(new Headers(request.headers).get("x-csrf-token")).toBe("csrf-token");
  });
});
