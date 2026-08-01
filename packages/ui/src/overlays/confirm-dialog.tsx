"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";

import { Button } from "../primitives/button";

export function ConfirmDialog({
  cancelLabel = "Cancel",
  confirmLabel,
  description,
  loading = false,
  onConfirm,
  onOpenChange,
  open,
  title,
}: {
  cancelLabel?: string;
  confirmLabel: string;
  description: ReactNode;
  loading?: boolean;
  onConfirm: () => void;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  title: string;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      openerRef.current = document.activeElement as HTMLElement | null;
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  function close() {
    onOpenChange(false);
    queueMicrotask(() => openerRef.current?.focus());
  }

  return (
    <dialog
      aria-describedby={descriptionId}
      aria-labelledby={titleId}
      className="m-auto w-[calc(100%_-_2rem)] max-w-lg rounded-2xl border border-line bg-surface p-0 text-foreground shadow-2xl backdrop:bg-navy/60"
      onCancel={(event) => {
        event.preventDefault();
        if (!loading) close();
      }}
      onClose={() => {
        if (open) onOpenChange(false);
      }}
      ref={dialogRef}
    >
      <div className="p-5 sm:p-6">
        <h2 className="text-lg font-black" id={titleId}>
          {title}
        </h2>
        <div className="mt-2 text-sm leading-6 text-muted" id={descriptionId}>
          {description}
        </div>
        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <Button
            autoFocus
            disabled={loading}
            onClick={close}
            variant="secondary"
          >
            {cancelLabel}
          </Button>
          <Button
            loading={loading}
            loadingLabel={`${confirmLabel}…`}
            onClick={onConfirm}
            variant="danger"
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </dialog>
  );
}
