"use client";

import { useState, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { RunControls } from "@/components/RunControls";
import { StatusTimeline } from "@/components/StatusTimeline";
import { MetricsCards } from "@/components/MetricsCards";
import { FailureTagChart } from "@/components/FailureTagChart";
import { WorstCasesTable } from "@/components/WorstCasesTable";
import { DiffSummary } from "@/components/DiffSummary";
import { ComparePanel } from "@/components/ComparePanel";
import { ExportButton } from "@/components/ExportButton";

import { useRunStatus } from "@/hooks/useRunStatus";
import { useRunResults } from "@/hooks/useRunResults";

const STORAGE_KEY = "autoeval_active_run_id";
const TERMINAL = new Set(["completed", "completed_with_errors", "failed"]);

export default function Dashboard() {
  const qc = useQueryClient();

  const [activeRunId, setActiveRunId] = useState<string | null>(null);

  // Restore run ID from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) setActiveRunId(stored);
  }, []);

  function handleRunStarted(runId: string) {
    setActiveRunId(runId);
    localStorage.setItem(STORAGE_KEY, runId);
    // Invalidate compare panel so it refreshes after next run completes
    qc.invalidateQueries({ queryKey: ["compare-latest"] });
  }

  function handleClearRun() {
    setActiveRunId(null);
    localStorage.removeItem(STORAGE_KEY);
  }

  const { data: run, isLoading: statusLoading } = useRunStatus(activeRunId);
  const { data: results } = useRunResults(activeRunId, run?.status);

  const isTerminal = run?.status !== undefined && TERMINAL.has(run.status);
  const metricsV1 = results?.metrics_v1 ?? run?.metrics_v1 ?? null;
  const metricsV2 = results?.metrics_v2 ?? run?.metrics_v2 ?? null;

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-8">
      {/* Header */}
      <header className="space-y-1">
        <h1 className="text-xl font-bold font-mono text-zinc-100 tracking-tight">
          AutoEval-Sum
        </h1>
        <p className="text-xs font-mono text-zinc-500">
          Autonomous evaluation suite improvement · summarization testing
        </p>
      </header>

      {/* Run Controls */}
      <section>
        <RunControls
          activeRunId={activeRunId}
          activeStatus={run?.status}
          onRunStarted={handleRunStarted}
        />
      </section>

      {/* Active / completed run status */}
      {activeRunId && (
        <section className="space-y-3">
          {statusLoading && (
            <p className="text-xs font-mono text-zinc-600">
              Loading run status…
            </p>
          )}
          {run && <StatusTimeline run={run} />}

          {isTerminal && (
            <div className="flex items-center gap-4">
              <ExportButton runId={activeRunId} />
              <button
                onClick={handleClearRun}
                className="text-xs font-mono text-zinc-600 hover:text-zinc-400 transition-colors"
              >
                Clear / start new run
              </button>
            </div>
          )}
        </section>
      )}

      {/* Results panels — shown once run is terminal */}
      {isTerminal && (metricsV1 || metricsV2) && (
        <section className="space-y-6">
          <div className="border-t border-zinc-800 pt-6">
            <MetricsCards metricsV1={metricsV1} metricsV2={metricsV2} />
          </div>

          <FailureTagChart metricsV1={metricsV1} metricsV2={metricsV2} />
          <WorstCasesTable metricsV1={metricsV1} metricsV2={metricsV2} />

          {metricsV1 && metricsV2 && (
            <DiffSummary metricsV1={metricsV1} metricsV2={metricsV2} />
          )}
        </section>
      )}

      {/* Historical comparison — always visible */}
      <section className="border-t border-zinc-800 pt-6">
        <ComparePanel />
      </section>
    </div>
  );
}
