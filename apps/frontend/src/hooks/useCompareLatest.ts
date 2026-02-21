"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useCompareLatest() {
  return useQuery({
    queryKey: ["compare-latest"],
    queryFn: api.compareLatest,
    retry: false,
    staleTime: 30_000,
  });
}
