"use client";

import { useCallback, useRef, useState } from "react";

export type IntentActivityToken = Readonly<{
  epoch: number;
  key: string;
}>;

/**
 * Track independent async intents without allowing an older settlement to
 * clear a newer request using the same key.
 */
export function useIntentActivity() {
  const epochs = useRef(new Map<string, number>());
  const [active, setActive] = useState<ReadonlySet<string>>(() => new Set());

  const begin = useCallback((key: string): IntentActivityToken => {
    const epoch = (epochs.current.get(key) ?? 0) + 1;
    epochs.current.set(key, epoch);
    setActive((current) => {
      const next = new Set(current);
      next.add(key);
      return next;
    });
    return { epoch, key };
  }, []);

  const end = useCallback((token: IntentActivityToken) => {
    if (epochs.current.get(token.key) !== token.epoch) return;
    setActive((current) => {
      if (!current.has(token.key)) return current;
      const next = new Set(current);
      next.delete(token.key);
      return next;
    });
  }, []);

  const isActive = useCallback((key: string) => active.has(key), [active]);

  return { begin, end, isActive };
}
