"use client";

import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

type InterviewPrepWorkspaceMetricsContextValue = {
  practiceLabCount: number;
  setPracticeLabCount: (count: number) => void;
};

const InterviewPrepWorkspaceMetricsContext =
  createContext<InterviewPrepWorkspaceMetricsContextValue | null>(null);

export function InterviewPrepWorkspaceMetricsProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [practiceLabCount, setPracticeLabCount] = useState(0);
  const value = useMemo(
    () => ({
      practiceLabCount,
      setPracticeLabCount,
    }),
    [practiceLabCount],
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
