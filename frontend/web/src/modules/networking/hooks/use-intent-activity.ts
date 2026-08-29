"use client";

import { useCallback, useRef, useState } from "react";

/**
 * Tracks independent mutations without letting an older settlement clear a
 * newer request. The ref is the synchronous duplicate-submission guard; state
 * is only the render projection.
 */
export function useIntentActivity() {
  const active = useRef(new Map<string, number>());
  const epochs = useRef(new Map<string, number>());
  const [activeKeys, setActiveKeys] = useState<ReadonlySet<string>>(
    () => new Set(),
  );

  const begin = useCallback((key: string): number | null => {
    if (active.current.has(key)) return null;
    const epoch = (epochs.current.get(key) ?? 0) + 1;
    epochs.current.set(key, epoch);
    active.current.set(key, epoch);
    setActiveKeys(new Set(active.current.keys()));
    return epoch;
  }, []);

  const finish = useCallback((key: string, epoch: number): void => {
    if (active.current.get(key) !== epoch) return;
    active.current.delete(key);
    setActiveKeys(new Set(active.current.keys()));
  }, []);

  const isBusy = useCallback(
    (key: string): boolean => activeKeys.has(key),
    [activeKeys],
  );

  return { begin, finish, isBusy };
}
