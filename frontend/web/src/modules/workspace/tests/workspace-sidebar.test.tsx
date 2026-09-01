import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceSectionNav } from "../components/workspace-section-nav";
import { WorkspaceSidebar } from "../components/workspace-sidebar";
import {
  resolveWorkspaceContext,
  workspaceSections,
} from "../components/workspace-navigation";

const navigation = vi.hoisted(() => ({ pathname: "/interview-prep" }));

vi.mock("next/navigation", () => ({
  usePathname: () => navigation.pathname,
}));

describe("WorkspaceSidebar", () => {
  beforeEach(() => {
    navigation.pathname = "/interview-prep";
  });

  it("presents exactly the seven consolidated destinations", () => {
    render(<WorkspaceSidebar />);

    const rail = screen.getByRole("navigation", {
      name: "Application navigation",
    });
    const labels = screen
      .getAllByRole("link")
      .filter((link) => rail.contains(link))
      .map((link) => link.textContent?.trim());

    expect(labels).toEqual([
      "Home",
      "Profile",
      "Resumes",
      "Job search",
      "Applications",
      "Interview prep",
      "Growth",
    ]);
  });

  it("highlights the owning section from a nested route", () => {
    navigation.pathname = "/networking/contacts/contact-id";

    render(<WorkspaceSidebar />);

    expect(
      screen.getByRole("link", { name: "Interview prep" }),
    ).toHaveAttribute("aria-current", "page");
  });

  it("highlights Profile from an evidence route", () => {
    navigation.pathname = "/evidence/00000000-0000-4000-8000-000000000001";

    render(<WorkspaceSidebar />);

    expect(screen.getByRole("link", { name: "Profile" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("keeps collapsed destinations accessible by name", () => {
    navigation.pathname = "/analytics";

    render(<WorkspaceSidebar collapsed />);

    expect(screen.getByRole("link", { name: "Growth" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Resumes" })).toBeInTheDocument();
  });
});

describe("WorkspaceSectionNav", () => {
  it("exposes the sibling tools a section owns", () => {
    navigation.pathname = "/interview-prep";

    render(<WorkspaceSectionNav />);

    expect(
      screen.getByRole("link", { name: "Interview Prep" }),
    ).toHaveAttribute("href", "/interview-prep");
    expect(screen.getByRole("link", { name: "Networking" })).toHaveAttribute(
      "href",
      "/networking",
    );
    expect(
      screen.getByRole("link", { name: "Interview Prep" }),
    ).toHaveAttribute("aria-current", "page");
  });

  it("prefers the deepest matching tool", () => {
    navigation.pathname = "/career-profile/imports";

    render(<WorkspaceSectionNav />);

    expect(
      screen.getByRole("link", { name: "Resume Imports" }),
    ).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Profile" })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("exposes Job search sibling tools", () => {
    navigation.pathname = "/job-match/saved";

    render(<WorkspaceSectionNav />);

    expect(screen.getByRole("link", { name: "Job search" })).toHaveAttribute(
      "href",
      "/job-match",
    );
    expect(screen.getByRole("link", { name: "Saved jobs" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Role matching" })).toHaveAttribute(
      "href",
      "/job-match/roles",
    );
  });

  it("renders nothing for a single-tool section", () => {
    navigation.pathname = "/applications";

    const { container } = render(<WorkspaceSectionNav />);

    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing outside the workspace sections", () => {
    navigation.pathname = "/settings/security";

    const { container } = render(<WorkspaceSectionNav />);

    expect(container).toBeEmptyDOMElement();
  });
});

describe("workspace navigation model", () => {
  it("keeps every previously reachable workspace route addressable", () => {
    const reachable = new Set(
      workspaceSections.flatMap((section) => [
        section.href,
        ...section.tools.map(({ href }) => href),
      ]),
    );

    for (const href of [
      "/dashboard",
      "/career-profile",
      "/evidence",
      "/achievement-inbox",
      // Role Explorer was merged into Job search Role matching.
      "/job-match",
      "/job-match/saved",
      "/job-match/roles",
      "/applications",
      // Resume Builder and Change Studio were merged into the Resume Studio
      // page the same way; /resume-builder redirects there, and
      // /change-studio remains a deep-linkable detail route reached from a
      // link on the page rather than the nav's own tools list.
      "/resume-health/account",
      "/interview-prep",
      "/networking",
      "/career-growth",
      "/analytics",
    ]) {
      expect(reachable.has(href)).toBe(true);
    }
  });

  it("reports the section, tool, and orientation copy for the top bar", () => {
    expect(resolveWorkspaceContext("/evidence")).toMatchObject({
      group: "Profile",
      label: "Evidence Vault",
      subtitle: "Your career source of truth",
    });
    expect(resolveWorkspaceContext("/applications")).toMatchObject({
      group: "Applications",
      label: "Applications",
      subtitle: "Track every application",
    });
    expect(resolveWorkspaceContext("/settings")).toMatchObject({
      group: "Account",
      label: "Settings",
      subtitle: "Manage your account",
    });
  });

  it("gives every section an icon and a subtitle for the top bar", () => {
    for (const section of workspaceSections) {
      expect(section.subtitle.length).toBeGreaterThan(0);
      expect(resolveWorkspaceContext(section.href).icon).toBe(section.icon);
    }
  });
});
