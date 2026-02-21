"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { RunStatus } from "@/lib/types";

const ACTIVE_STATUSES: RunStatus[] = ["queued", "running"];

export function useRunStatus(runId: string | null) {
  return useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.getRunStatus(runId!),
    enabled: runId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ACTIVE_STATUSES.includes(status) ? 3000 : false;
    },
  });
}
