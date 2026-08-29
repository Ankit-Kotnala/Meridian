"use client";

import { Copy, Download, ImageDown } from "lucide-react";
import { useState } from "react";

import { Button } from "@rezumi/ui";

import type { CorpIdChecks } from "@/shared/identity/corp-id";
import {
  CREDENTIAL_HEIGHT,
  CREDENTIAL_WIDTH,
  credentialFileName,
  credentialSvg,
} from "@/shared/identity/corp-id-credential";

function saveBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.download = fileName;
  link.href = url;
  link.rel = "noopener";
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/** Rasterize the credential at 2x so it stays crisp when shared or printed. */
async function svgToPng(svg: string): Promise<Blob> {
  const scale = 2;
  const source = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
  const image = new Image();
  image.decoding = "sync";
  await new Promise<void>((resolve, reject) => {
    image.addEventListener("load", () => resolve(), { once: true });
    image.addEventListener(
      "error",
      () => reject(new Error("The credential image could not be rendered.")),
      { once: true },
    );
    image.src = source;
  });

  const canvas = document.createElement("canvas");
  canvas.width = CREDENTIAL_WIDTH * scale;
  canvas.height = CREDENTIAL_HEIGHT * scale;
  const context = canvas.getContext("2d");
  if (!context)
    throw new Error("This browser cannot rasterize the credential.");
  context.scale(scale, scale);
  context.drawImage(image, 0, 0, CREDENTIAL_WIDTH, CREDENTIAL_HEIGHT);

  return await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob);
      else reject(new Error("The credential image could not be encoded."));
    }, "image/png");
  });
}

export function CorpIdCredentialCard({
  checks,
  corpId,
  displayName,
}: {
  checks: CorpIdChecks;
  corpId: string;
  displayName: string;
}) {
  const [copied, setCopied] = useState(false);
  const [failure, setFailure] = useState<string>();

  const svg = credentialSvg({
    checks,
    corpId,
    displayName,
    generatedOn: new Date().toISOString().slice(0, 10),
  });

  async function copyId() {
    try {
      await navigator.clipboard.writeText(corpId);
      setCopied(true);
      globalThis.setTimeout(() => setCopied(false), 2000);
    } catch {
      setFailure(
        "Your browser blocked clipboard access. Copy the ID manually.",
      );
    }
  }

  async function downloadPng() {
    setFailure(undefined);
    try {
      saveBlob(await svgToPng(svg), credentialFileName(corpId, "png"));
    } catch {
      setFailure(
        "This browser could not produce a PNG. The SVG download works everywhere.",
      );
    }
  }

  function downloadSvg() {
    setFailure(undefined);
    saveBlob(
      new Blob([svg], { type: "image/svg+xml;charset=utf-8" }),
      credentialFileName(corpId, "svg"),
    );
  }

  return (
    <div className="space-y-4">
      {/* The artifact is theme-independent by design, so it is injected as-is. */}
      <div
        className="overflow-hidden rounded-[var(--radius-card)] shadow-[var(--shadow-md)] [&>svg]:block [&>svg]:h-auto [&>svg]:w-full"
        dangerouslySetInnerHTML={{ __html: svg }}
      />

      <div className="flex flex-wrap gap-2">
        <Button onClick={() => void downloadPng()}>
          <ImageDown aria-hidden="true" className="size-4" />
          Download PNG
        </Button>
        <Button onClick={downloadSvg} variant="secondary">
          <Download aria-hidden="true" className="size-4" />
          Download SVG
        </Button>
        <Button onClick={() => void copyId()} variant="secondary">
          <Copy aria-hidden="true" className="size-4" />
          {copied ? "Copied" : "Copy ID"}
        </Button>
      </div>

      {failure && (
        <p className="text-xs leading-5 text-danger" role="status">
          {failure}
        </p>
      )}
    </div>
  );
}
