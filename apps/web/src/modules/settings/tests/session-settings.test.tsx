import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SessionSettings } from "../views/session-settings";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn(), replace: vi.fn() }),
}));

function json(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

describe("session settings", () => {
  afterEach(() => {
    document.cookie = "careeros_csrf=; Max-Age=0; Path=/";
    vi.unstubAllGlobals();
  });

  it("lists real session state and revokes a selected non-current session", async () => {
    document.cookie = "careeros_csrf=session-csrf; Path=/";
    const fetchMock = vi.fn(
      async (input: string | URL | Request, init?: RequestInit) => {
        const url = String(input);
        if (
          url.endsWith("/api/v1/auth/sessions") &&
          (!init?.method || init.method === "GET")
        ) {
          return json({
            data: [
              {
                authMethod: "password",
                createdAt: "2026-07-15T09:00:00Z",
                current: true,
                deviceLabel: "Current browser",
                expiresAt: "2026-08-15T09:00:00Z",
                id: "00000000-0000-4000-8000-000000000001",
                lastSeenAt: "2026-07-15T09:30:00Z",
              },
              {
                authMethod: "google",
                createdAt: "2026-07-14T09:00:00Z",
                current: false,
                deviceLabel: "Other browser",
                expiresAt: "2026-08-14T09:00:00Z",
                id: "00000000-0000-4000-8000-000000000002",
                lastSeenAt: "2026-07-14T09:30:00Z",
              },
            ],
          });
        }
        if (url.includes("000000000002") && init?.method === "DELETE") {
          return new Response(null, { status: 204 });
        }
        throw new Error(`Unexpected request: ${url}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<SessionSettings />);

    expect(await screen.findByText("Other browser")).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Revoke Other browser" }),
    );

    await waitFor(() =>
      expect(screen.queryByText("Other browser")).not.toBeInTheDocument(),
    );
    expect(screen.getByText("Other browser was signed out.")).toBeVisible();
  });
});
