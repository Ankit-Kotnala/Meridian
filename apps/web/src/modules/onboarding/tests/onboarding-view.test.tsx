import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OnboardingView } from "../views/onboarding-view";

const replace = vi.fn();
const refresh = vi.fn();
const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh, replace }),
}));

const initial = {
  currentStep: "profile",
  displayName: "Alex Morgan",
  industry: null,
  language: "en",
  parsedReviewHandoff: "notStarted",
  preferredLocation: null,
  resumeHandoff: "notStarted",
  seniority: null,
  skippedSteps: [],
  status: "inProgress",
  targetRole: null,
  version: 1,
  workModel: null,
  writingStyle: "balanced",
};

function json(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

describe("onboarding", () => {
  afterEach(() => {
    document.cookie = "careeros_csrf=; Max-Age=0; Path=/";
    vi.unstubAllGlobals();
    replace.mockReset();
    refresh.mockReset();
    push.mockReset();
  });

  it("persists each honest handoff before completing preferences", async () => {
    document.cookie = "careeros_csrf=session-csrf; Path=/";
    let state = { ...initial };
    const fetchMock = vi.fn(
      async (input: string | URL | Request, init?: RequestInit) => {
        const url = String(input);
        if (
          url.endsWith("/api/v1/onboarding") &&
          (!init?.method || init.method === "GET")
        ) {
          return json(state);
        }
        if (url.endsWith("/api/v1/onboarding") && init?.method === "PATCH") {
          state = {
            ...state,
            ...(JSON.parse(String(init.body)) as typeof state),
            version: state.version + 1,
          };
          return json(state);
        }
        throw new Error(`Unexpected request: ${url}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<OnboardingView />);

    expect(
      await screen.findByRole("heading", { name: "Confirm your profile name" }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /save and continue/i }));

    expect(
      await screen.findByRole("heading", {
        name: "Resume upload is not active yet",
      }),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: /continue without a resume/i }),
    );

    expect(
      await screen.findByRole("heading", {
        name: "Parsed review has no data yet",
      }),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: /continue to preferences/i }),
    );

    expect(
      await screen.findByRole("heading", {
        name: "Choose working preferences",
      }),
    ).toBeVisible();
    fireEvent.change(screen.getByLabelText("Target role (optional)"), {
      target: { value: "Product manager" },
    });
    fireEvent.click(screen.getByRole("button", { name: /finish onboarding/i }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
    expect(state.status).toBe("completed");
    expect(state.resumeHandoff).toBe("skipped");
    expect(state.parsedReviewHandoff).toBe("skipped");
    expect(state.targetRole).toBe("Product manager");
  });
});
