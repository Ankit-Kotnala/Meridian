"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { requestErrorMessage } from "@/shared/api/browser-request";

import {
  getSettingsCapabilities,
  type SettingsCapabilities,
} from "../api/settings-api";

type SettingsCapabilitiesContextValue = {
  capabilities: SettingsCapabilities | undefined;
  failure: string | undefined;
  loading: boolean;
  reload: () => Promise<void>;
};

const SettingsCapabilitiesContext =
  createContext<SettingsCapabilitiesContextValue | null>(null);

export function SettingsCapabilitiesProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [capabilities, setCapabilities] = useState<SettingsCapabilities>();
  const [failure, setFailure] = useState<string>();
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setCapabilities(await getSettingsCapabilities());
      setFailure(undefined);
    } catch (error) {
      setFailure(
        requestErrorMessage(error, "We couldn’t load settings capabilities."),
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void reload());
  }, [reload]);

  const value = useMemo(
    () => ({ capabilities, failure, loading, reload }),
    [capabilities, failure, loading, reload],
  );

  return (
    <SettingsCapabilitiesContext.Provider value={value}>
      {children}
    </SettingsCapabilitiesContext.Provider>
  );
}

export function useSettingsCapabilities() {
  const context = useContext(SettingsCapabilitiesContext);
  if (!context) {
    throw new Error(
      "useSettingsCapabilities must be used within SettingsCapabilitiesProvider.",
    );
  }
  return context;
}
