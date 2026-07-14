"use client";

import { useEffect, useRef } from "react";

import { Alert } from "@careeros/ui";

export function FormErrorSummary({
  message,
}: {
  message?: string | undefined;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (message) ref.current?.focus();
  }, [message]);

  if (!message) return null;
  return (
    <div ref={ref} tabIndex={-1}>
      <Alert title="We couldn’t complete that request" tone="danger">
        {message}
      </Alert>
    </div>
  );
}
