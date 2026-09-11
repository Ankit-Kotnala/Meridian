import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceTopBar } from "../components/workspace-top-bar";

const navigation = vi.hoisted(() => ({ pathname: "/dashboard" }));

vi.mock("next/navigation", () => ({
  usePathname: () => navigation.pathname,
}));

const viewer = {
  displayName: "Ankit Kotnala",
  email: "ankit.kotnala12@gmail.com",
  id: "00000000-0000-4000-8000-000000000001",
};

describe("WorkspaceTopBar account menu", () => {
  beforeEach(() => {
    navigation.pathname = "/dashboard";
  });

  it("closes when clicking outside the menu", () => {
    render(
      <>
        <WorkspaceTopBar
          accountActions={<button type="button">Sign out</button>}
          menuButtonRef={{ current: null }}
          onOpenMenu={() => undefined}
          viewer={viewer}
        />
        <button type="button">Outside target</button>
      </>,
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Account menu for Ankit Kotnala" }),
    );
    expect(screen.getByRole("menu")).toBeVisible();

    fireEvent.pointerDown(screen.getByRole("button", { name: "Outside target" }));
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("closes on Escape and returns focus to the trigger", () => {
    render(
      <WorkspaceTopBar
        accountActions={<button type="button">Sign out</button>}
        menuButtonRef={{ current: null }}
        onOpenMenu={() => undefined}
        viewer={viewer}
      />,
    );

    const trigger = screen.getByRole("button", {
      name: "Account menu for Ankit Kotnala",
    });
    fireEvent.click(trigger);
    expect(screen.getByRole("menu")).toBeVisible();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});
