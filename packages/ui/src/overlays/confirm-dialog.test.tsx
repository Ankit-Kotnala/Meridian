import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { ConfirmDialog } from "./confirm-dialog";

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal() {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function close() {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  };
});

describe("ConfirmDialog", () => {
  it("has an accessible name and requires an explicit confirmation", () => {
    const onConfirm = vi.fn();
    const onOpenChange = vi.fn();
    render(
      <ConfirmDialog
        confirmLabel="Delete resume"
        description="The source and derived report will be removed."
        onConfirm={onConfirm}
        onOpenChange={onOpenChange}
        open
        title="Delete this resume?"
      />,
    );

    expect(
      screen.getByRole("dialog", { name: "Delete this resume?" }),
    ).toHaveAccessibleDescription(
      "The source and derived report will be removed.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Delete resume" }));
    expect(onConfirm).toHaveBeenCalledOnce();
    expect(onOpenChange).not.toHaveBeenCalled();
  });
});
