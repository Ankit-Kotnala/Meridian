import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Tabs } from "./tabs";

describe("Tabs", () => {
  it("supports arrow, Home, and End keyboard navigation", () => {
    render(
      <Tabs
        label="Resume views"
        tabs={[
          { id: "structured", label: "Structured", panel: "Structured panel" },
          { id: "plain", label: "Plain text", panel: "Plain panel" },
          { id: "order", label: "Reading order", panel: "Order panel" },
        ]}
      />,
    );

    const structured = screen.getByRole("tab", { name: "Structured" });
    structured.focus();
    fireEvent.keyDown(structured, { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Plain text" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByText("Plain panel")).toBeVisible();

    fireEvent.keyDown(document.activeElement!, { key: "End" });
    expect(screen.getByRole("tab", { name: "Reading order" })).toHaveFocus();
    fireEvent.keyDown(document.activeElement!, { key: "Home" });
    expect(structured).toHaveFocus();
  });
});
