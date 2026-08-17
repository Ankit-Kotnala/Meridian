import { render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CorpIdCard } from "../components/corp-id-card";

const USER_ID = "00000000-0000-4000-8000-0000000003e7";

function json(body: unknown) {
  return new Response(JSON.stringify(body), {
    headers: { "content-type": "application/json" },
    status: 200,
  });
}

function stubApi(
  evidence: readonly unknown[],
  experiences: readonly unknown[],
) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/evidence")) {
        return Promise.resolve(json({ data: evidence }));
      }
      if (url.includes("/api/v1/experiences")) {
        return Promise.resolve(json({ data: experiences }));
      }
      return Promise.resolve(new Response("{}", { status: 404 }));
    }),
  );
}

describe("Corp ID card", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the derived identifier with the scope disclaimer", async () => {
    stubApi([], []);

    render(<CorpIdCard emailVerified userId={USER_ID} />);

    const card = screen.getByRole("region", { name: "Rezumi Corp ID" });
    expect(
      within(card).getByText(/^RZ-[0-9A-Z]{5}-[0-9A-Z]{5}$/),
    ).toBeVisible();
    expect(
      within(card).getByText(/not an employer credential, a background check/i),
    ).toBeVisible();
  });

  it("raises standing to Evidenced once confirmed evidence exists", async () => {
    stubApi([{ state: "confirmed" }], [{ id: "experience-1" }]);

    render(<CorpIdCard emailVerified userId={USER_ID} />);

    await waitFor(() => {
      expect(screen.getByText("Evidenced")).toBeVisible();
    });
    expect(screen.queryByText(/^Next: /)).not.toBeInTheDocument();
  });

  it("names the next check when standing can still rise", async () => {
    stubApi([{ state: "inferred" }], [{ id: "experience-1" }]);

    render(<CorpIdCard emailVerified userId={USER_ID} />);

    await waitFor(() => {
      expect(screen.getByText("Profiled")).toBeVisible();
    });
    expect(
      screen.getByText(/Confirm at least one evidence record/),
    ).toBeVisible();
  });

  it("withholds standing while the email is unconfirmed", async () => {
    stubApi([{ state: "confirmed" }], [{ id: "experience-1" }]);

    render(<CorpIdCard emailVerified={false} userId={USER_ID} />);

    expect(screen.getByText("Unverified")).toBeVisible();
    expect(screen.getByText(/Confirm your email address\./)).toBeVisible();
  });

  it("degrades to the lowest standing when the counts cannot be read", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("offline"))),
    );

    render(<CorpIdCard emailVerified userId={USER_ID} />);

    await waitFor(() => {
      expect(screen.getByText("Registered")).toBeVisible();
    });
  });

  it("renders nothing when the account identifier is not derivable", () => {
    stubApi([], []);

    const { container } = render(
      <CorpIdCard emailVerified userId="not-a-uuid" />,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
