import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceSidebar } from "../components/workspace-sidebar";

const navigation = vi.hoisted(() => ({ pathname: "/interview-prep" }));

vi.mock("next/navigation", () => ({
  usePathname: () => navigation.pathname,
}));

describe("WorkspaceSidebar", () => {
  beforeEach(() => {
    navigation.pathname = "/interview-prep";
  });

  it("exposes every Phase 9 workspace as a live navigation destination", () => {
    render(<WorkspaceSidebar />);

    expect(
      screen.getByRole("link", { name: "Interview Prep" }),
    ).toHaveAttribute("href", "/interview-prep");
    expect(screen.getByRole("link", { name: "Networking" })).toHaveAttribute(
      "href",
      "/networking",
    );
    expect(screen.getByRole("link", { name: "Career Growth" })).toHaveAttribute(
      "href",
      "/career-growth",
    );
    expect(screen.getByRole("link", { name: "Analytics" })).toHaveAttribute(
      "href",
      "/analytics",
    );
    expect(
      screen.getByRole("link", { name: "Interview Prep" }),
    ).toHaveAttribute("aria-current", "page");
    expect(
      screen.queryByText("Coming later", { exact: true }),
    ).not.toBeInTheDocument();
  });

  it("keeps collapsed navigation destinations accessible by name", () => {
    navigation.pathname = "/networking/contacts/contact-id";

    render(<WorkspaceSidebar collapsed />);

    expect(screen.getByRole("link", { name: "Networking" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(
      screen.getByRole("link", { name: "Career Growth" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Analytics" })).toBeInTheDocument();
  });
});
