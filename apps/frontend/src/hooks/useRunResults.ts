"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { RunStatus } from "@/lib/types";

const TERMINAL_STATUSES: RunStatus[] = [
  "completed",
  "completed_with_errors",
  "failed",
];

export function useRunResults(runId: string | null, status: RunStatus | undefined) {
  const isTerminal = status !== undefined && TERMINAL_STATUSES.includes(status);

  return useQuery({
    queryKey: ["run-results", runId],
    queryFn: () => api.getRunResults(runId!),
    enabled: runId !== null && isTerminal,
    staleTime: Infinity,
  });
}
