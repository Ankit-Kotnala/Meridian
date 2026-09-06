"use client";

import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

type InterviewPrepWorkspaceMetricsContextValue = {
  libraryResourceCount: number;
  setLibraryResourceCount: (count: number) => void;
};

const InterviewPrepWorkspaceMetricsContext =
  createContext<InterviewPrepWorkspaceMetricsContextValue | null>(null);

export function InterviewPrepWorkspaceMetricsProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [libraryResourceCount, setLibraryResourceCount] = useState(0);
  const value = useMemo(
    () => ({
      libraryResourceCount,
      setLibraryResourceCount,
    }),
    [libraryResourceCount],
  );

  return (
    <InterviewPrepWorkspaceMetricsContext.Provider value={value}>
      {children}
    </InterviewPrepWorkspaceMetricsContext.Provider>
  );
}

export function useInterviewPrepWorkspaceMetrics() {
  return useContext(InterviewPrepWorkspaceMetricsContext);
}
