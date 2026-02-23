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

const CORPUS_MIN = 50;
const CORPUS_MAX = 250;
const SUITE_MIN = 20;
const SUITE_MAX = 50;
const FIXED_SEED = 42;

export function RunControls({ activeRunId, activeStatus, onRunStarted }: Props) {
  const qc = useQueryClient();
  const [corpusSize, setCorpusSize] = useState(150);
  const [suiteSize, setSuiteSize] = useState(20);

  const startMutation = useMutation({
    mutationFn: () =>
      api.startRun({ seed: FIXED_SEED, corpus_size: corpusSize, suite_size: suiteSize }),
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

  const isActive = activeStatus === "queued" || activeStatus === "running";

  const handleCorpusChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = Number(e.target.value);
    setCorpusSize(Math.min(CORPUS_MAX, Math.max(CORPUS_MIN, v)));
  };

  const handleSuiteChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = Number(e.target.value);
    setSuiteSize(Math.min(SUITE_MAX, Math.max(SUITE_MIN, v)));
  };

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 backdrop-blur-sm">
      <div className="grid grid-cols-3 gap-4 mb-5">
        {/* Seed — locked */}
        <div className="space-y-1.5">
          <div>
            <span className="text-xs font-mono font-medium text-zinc-300">Seed</span>
            <span className="text-xs font-mono text-zinc-600 ml-2">fixed for reproducibility</span>
          </div>
          <div className="w-full rounded-lg bg-zinc-800/50 border border-zinc-700/50 px-3 py-2 text-sm font-mono text-zinc-500 select-none">
            {FIXED_SEED}
          </div>
        </div>

        {/* Corpus size */}
        <label className="space-y-1.5">
          <div>
            <span className="text-xs font-mono font-medium text-zinc-300">Corpus size</span>
            <span className="text-xs font-mono text-zinc-600 ml-2">{CORPUS_MIN}–{CORPUS_MAX} docs</span>
          </div>
          <input
            type="number"
            value={corpusSize}
            min={CORPUS_MIN}
            max={CORPUS_MAX}
            onChange={handleCorpusChange}
            disabled={isActive}
            className="w-full rounded-lg bg-zinc-800 border border-zinc-700 px-3 py-2 text-sm font-mono text-zinc-200 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          />
        </label>

        {/* Suite size */}
        <label className="space-y-1.5">
          <div>
            <span className="text-xs font-mono font-medium text-zinc-300">Suite size</span>
            <span className="text-xs font-mono text-zinc-600 ml-2">{SUITE_MIN}–{SUITE_MAX} cases</span>
          </div>
          <input
            type="number"
            value={suiteSize}
            min={SUITE_MIN}
            max={SUITE_MAX}
            onChange={handleSuiteChange}
            disabled={isActive}
            className="w-full rounded-lg bg-zinc-800 border border-zinc-700 px-3 py-2 text-sm font-mono text-zinc-200 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          />
        </label>
      </div>

      <div className="flex items-center gap-3">
        {!isActive ? (
          <button
            onClick={() => startMutation.mutate()}
            disabled={startMutation.isPending}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 px-5 py-2 text-sm font-semibold text-white transition-colors shadow-lg shadow-indigo-900/30"
          >
            {startMutation.isPending ? (
              <>
                <SpinIcon /> Starting…
              </>
            ) : (
              <>
                <PlayIcon /> Start Run
              </>
            )}
          </button>
        ) : (
          <button
            onClick={() => cancelMutation.mutate()}
            disabled={cancelMutation.isPending}
            className="inline-flex items-center gap-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 disabled:opacity-50 px-5 py-2 text-sm font-semibold text-zinc-300 transition-colors"
          >
            <StopIcon /> {cancelMutation.isPending ? "Cancelling…" : "Cancel Run"}
          </button>
        )}

        {startMutation.isError && (
          <p className="text-xs text-red-400 font-mono bg-red-950/50 border border-red-900 rounded px-3 py-1.5">
            Failed to start — is the backend reachable?
          </p>
        )}
        {cancelMutation.isError && (
          <p className="text-xs text-red-400 font-mono">Cancel request failed.</p>
        )}
      </div>
    </div>
  );
}

function PlayIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
      <path d="M6.3 2.84A1.5 1.5 0 004 4.11v11.78a1.5 1.5 0 002.3 1.27l9.344-5.891a1.5 1.5 0 000-2.538L6.3 2.84z" />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
      <path fillRule="evenodd" d="M4.5 4.5a1 1 0 011-1h9a1 1 0 011 1v9a1 1 0 01-1 1h-9a1 1 0 01-1-1v-9z" clipRule="evenodd" />
    </svg>
  );
}

function SpinIcon() {
  return (
    <svg className="animate-spin w-3.5 h-3.5" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}
