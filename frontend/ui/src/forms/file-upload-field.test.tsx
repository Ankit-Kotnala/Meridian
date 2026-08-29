import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FileUploadField, formatBytes } from "./file-upload-field";

describe("FileUploadField", () => {
  it("keeps the native input labelled and reports the selected file", () => {
    const onFileChange = vi.fn();
    const { rerender } = render(
      <FileUploadField
        accept="application/pdf"
        error="Choose a supported file."
        hint="Maximum 10 MB."
        id="resume"
        label="Resume file"
        onFileChange={onFileChange}
      />,
    );
    const input = screen.getByLabelText("Resume file");
    expect(input).toHaveAccessibleDescription(
      "Maximum 10 MB. Choose a supported file.",
    );
    expect(input).toHaveAttribute("aria-invalid", "true");

    const file = new File(["fictional resume"], "fictional-resume.pdf", {
      type: "application/pdf",
    });
    fireEvent.change(input, { target: { files: [file] } });
    expect(onFileChange).toHaveBeenCalledWith(file);

    rerender(
      <FileUploadField
        id="resume"
        label="Resume file"
        onFileChange={onFileChange}
        selectedFile={file}
      />,
    );
    expect(screen.getByText("fictional-resume.pdf")).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: "Remove fictional-resume.pdf" }),
    );
    expect(onFileChange).toHaveBeenLastCalledWith(undefined);
  });

  it("formats sizes without exposing imprecise raw byte strings", () => {
    expect(formatBytes(500)).toBe("500 B");
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
  });
});
