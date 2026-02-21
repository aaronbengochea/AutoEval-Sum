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

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) setActiveRunId(stored);
  }, []);

  function handleRunStarted(runId: string) {
    setActiveRunId(runId);
    localStorage.setItem(STORAGE_KEY, runId);
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
    <div className="relative z-10 min-h-screen">
      {/* Top nav bar */}
      <header className="border-b border-zinc-800/60 bg-zinc-950/80 backdrop-blur-sm sticky top-0 z-20">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center">
              <span className="text-white text-xs font-bold">AE</span>
            </div>
            <span className="font-semibold text-zinc-100 tracking-tight">
              AutoEval<span className="text-indigo-400">-Sum</span>
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-zinc-600 px-2 py-1 rounded bg-zinc-900 border border-zinc-800">
              gemini-2.0-flash · temp=0
            </span>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-10 space-y-10">

        {/* Hero section */}
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <div className="h-px flex-1 bg-gradient-to-r from-indigo-600/50 to-transparent" />
            <span className="text-xs font-mono text-indigo-400 uppercase tracking-widest">
              Autonomous Eval Loop
            </span>
            <div className="h-px flex-1 bg-gradient-to-l from-indigo-600/50 to-transparent" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-zinc-100">
            Summarization Eval Suite Improvement
          </h1>
          <p className="text-zinc-500 text-sm max-w-2xl leading-relaxed">
            Runs a two-iteration evaluation loop: a baseline suite is generated and judged,
            then a curriculum agent produces an improved v2 suite targeting the detected failure modes.
          </p>

          {/* Pipeline steps */}
          <div className="flex items-center gap-1.5 flex-wrap pt-1">
            {[
              "Load Corpus",
              "Eval Author v1",
              "Judge v1",
              "Curriculum",
              "Eval Author v2",
              "Judge v2",
              "Finalize",
            ].map((step, i, arr) => (
              <div key={step} className="flex items-center gap-1.5">
                <span className="text-xs font-mono text-zinc-500 bg-zinc-900 border border-zinc-800 rounded px-2 py-0.5">
                  {step}
                </span>
                {i < arr.length - 1 && (
                  <span className="text-zinc-700 text-xs">→</span>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* Run controls */}
        <section>
          <SectionHeading label="Run Controls" />
          <RunControls
            activeRunId={activeRunId}
            activeStatus={run?.status}
            onRunStarted={handleRunStarted}
          />
        </section>

        {/* Active run status */}
        {activeRunId && (
          <section className="space-y-4">
            <SectionHeading label="Run Status" />
            {statusLoading && !run && (
              <div className="flex items-center gap-2 text-sm text-zinc-600">
                <Spinner /> Loading run status…
              </div>
            )}
            {run && <StatusTimeline run={run} />}
            {isTerminal && (
              <div className="flex items-center gap-4 pt-1">
                <ExportButton runId={activeRunId} />
                <button
                  onClick={handleClearRun}
                  className="text-xs font-mono text-zinc-600 hover:text-zinc-400 transition-colors underline underline-offset-2"
                >
                  Clear and start new run
                </button>
              </div>
            )}
          </section>
        )}

        {/* Results — shown after run completes */}
        {isTerminal && (metricsV1 || metricsV2) && (
          <>
            <Divider />

            <section className="space-y-4">
              <SectionHeading label="Suite Metrics" badge="v1 → v2" />
              <MetricsCards metricsV1={metricsV1} metricsV2={metricsV2} />
            </section>

            <section className="space-y-4">
              <SectionHeading label="Failure Mode Distribution" />
              <FailureTagChart metricsV1={metricsV1} metricsV2={metricsV2} />
            </section>

            {metricsV1 && metricsV2 && (
              <section className="space-y-4">
                <SectionHeading label="Improvement Diff" />
                <DiffSummary metricsV1={metricsV1} metricsV2={metricsV2} />
              </section>
            )}

            <section className="space-y-4">
              <SectionHeading label="Worst Cases" />
              <WorstCasesTable metricsV1={metricsV1} metricsV2={metricsV2} />
            </section>
          </>
        )}

        {/* Historical comparison — always visible */}
        <Divider />
        <section className="space-y-4">
          <SectionHeading label="Latest Run Comparison" />
          <ComparePanel />
        </section>

      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-800/60 mt-16">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <span className="text-xs font-mono text-zinc-700">
            AutoEval-Sum v0.1.0
          </span>
          <span className="text-xs font-mono text-zinc-700">
            seed=42 · corpus=150 · suite=20
          </span>
        </div>
      </footer>
    </div>
  );
}

function SectionHeading({ label, badge }: { label: string; badge?: string }) {
  return (
    <div className="flex items-center gap-3 mb-2">
      <h2 className="text-xs font-mono font-semibold text-zinc-400 uppercase tracking-widest">
        {label}
      </h2>
      {badge && (
        <span className="text-xs font-mono bg-indigo-950 text-indigo-400 border border-indigo-800 rounded-full px-2 py-0.5">
          {badge}
        </span>
      )}
      <div className="h-px flex-1 bg-zinc-800" />
    </div>
  );
}

function Divider() {
  return <div className="h-px bg-gradient-to-r from-transparent via-zinc-800 to-transparent" />;
}

function Spinner() {
  return (
    <svg
      className="animate-spin h-3.5 w-3.5 text-indigo-400"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12" cy="12" r="10"
        stroke="currentColor" strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v8H4z"
      />
    </svg>
  );
}
