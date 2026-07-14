import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Button } from "../primitives/button";
import { CheckboxField } from "./checkbox-field";
import { TextField } from "./text-field";

describe("form controls", () => {
  it("associates text field help and errors with the input", () => {
    render(
      <TextField
        error="Enter a valid email address."
        hint="We use this address to verify your account."
        id="email"
        label="Email"
        type="email"
      />,
    );

    const input = screen.getByRole("textbox", { name: "Email" });
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription(
      "We use this address to verify your account. Enter a valid email address.",
    );
  });

  it("provides an accessible checkbox label and description", () => {
    render(
      <CheckboxField
        description="You can change this later."
        id="consent"
        label="Allow product email"
      />,
    );

    expect(
      screen.getByRole("checkbox", { name: "Allow product email" }),
    ).toHaveAccessibleDescription("You can change this later.");
  });

  it("disables a busy button while preserving its status text", () => {
    const onClick = vi.fn();
    render(
      <Button loading loadingLabel="Signing in…" onClick={onClick}>
        Sign in
      </Button>,
    );

    const button = screen.getByRole("button", { name: "Signing in…" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });
});
