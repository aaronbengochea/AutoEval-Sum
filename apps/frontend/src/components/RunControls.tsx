"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { RunStatus } from "@/lib/types";

interface Props {
  activeRunId: string | null;
  activeStatus: RunStatus | undefined;
  onRunStarted: (runId: string) => void;
}

export function RunControls({ activeRunId, activeStatus, onRunStarted }: Props) {
  const qc = useQueryClient();

  const [seed, setSeed] = useState(42);
  const [corpusSize, setCorpusSize] = useState(150);
  const [suiteSize, setSuiteSize] = useState(20);

  const startMutation = useMutation({
    mutationFn: () =>
      api.startRun({ seed, corpus_size: corpusSize, suite_size: suiteSize }),
    onSuccess: (data) => {
      onRunStarted(data.run_id);
      qc.invalidateQueries({ queryKey: ["run", data.run_id] });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: () => api.cancelRun(activeRunId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["run", activeRunId] });
    },
  });

  const isActive =
    activeStatus === "queued" || activeStatus === "running";

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 space-y-4">
      <h2 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">
        Run Controls
      </h2>

      <div className="grid grid-cols-3 gap-3">
        <label className="space-y-1">
          <span className="text-xs font-mono text-zinc-500">Seed</span>
          <input
            type="number"
            value={seed}
            onChange={(e) => setSeed(Number(e.target.value))}
            disabled={isActive}
            className="w-full rounded bg-zinc-800 border border-zinc-700 px-2 py-1.5 text-sm font-mono text-zinc-200 focus:outline-none focus:border-blue-500 disabled:opacity-40"
          />
        </label>
        <label className="space-y-1">
          <span className="text-xs font-mono text-zinc-500">Corpus</span>
          <input
            type="number"
            value={corpusSize}
            onChange={(e) => setCorpusSize(Number(e.target.value))}
            min={1}
            disabled={isActive}
            className="w-full rounded bg-zinc-800 border border-zinc-700 px-2 py-1.5 text-sm font-mono text-zinc-200 focus:outline-none focus:border-blue-500 disabled:opacity-40"
          />
        </label>
        <label className="space-y-1">
          <span className="text-xs font-mono text-zinc-500">Suite size</span>
          <input
            type="number"
            value={suiteSize}
            onChange={(e) => setSuiteSize(Number(e.target.value))}
            min={1}
            disabled={isActive}
            className="w-full rounded bg-zinc-800 border border-zinc-700 px-2 py-1.5 text-sm font-mono text-zinc-200 focus:outline-none focus:border-blue-500 disabled:opacity-40"
          />
        </label>
      </div>

      <div className="flex items-center gap-3">
        {!isActive ? (
          <button
            onClick={() => startMutation.mutate()}
            disabled={startMutation.isPending}
            className="rounded bg-blue-600 hover:bg-blue-500 disabled:opacity-50 px-4 py-2 text-sm font-semibold text-white transition-colors"
          >
            {startMutation.isPending ? "Starting…" : "Start Run"}
          </button>
        ) : (
          <button
            onClick={() => cancelMutation.mutate()}
            disabled={cancelMutation.isPending}
            className="rounded bg-zinc-700 hover:bg-zinc-600 disabled:opacity-50 px-4 py-2 text-sm font-semibold text-zinc-200 transition-colors"
          >
            {cancelMutation.isPending ? "Cancelling…" : "Cancel Run"}
          </button>
        )}

        {startMutation.isError && (
          <p className="text-xs text-red-400 font-mono">
            Failed to start run. Is the backend reachable?
          </p>
        )}
        {cancelMutation.isError && (
          <p className="text-xs text-red-400 font-mono">Cancel request failed.</p>
        )}
      </div>
    </div>
  );
}
