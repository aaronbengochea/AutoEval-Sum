"use client";

import type { RunStatus, RunStatusResponse } from "@/lib/types";

const STATUS_COLORS: Record<RunStatus, string> = {
  queued: "bg-zinc-600 text-zinc-200",
  running: "bg-blue-600 text-blue-100",
  completed: "bg-emerald-600 text-emerald-100",
  completed_with_errors: "bg-amber-600 text-amber-100",
  failed: "bg-red-700 text-red-100",
};

const STATUS_LABELS: Record<RunStatus, string> = {
  queued: "Queued",
  running: "Running",
  completed: "Completed",
  completed_with_errors: "Completed (errors)",
  failed: "Failed",
};

function fmtTs(ts: string | null): string {
  if (!ts) return "—";
  return new Date(ts).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

interface Props {
  run: RunStatusResponse;
}

export function StatusTimeline({ run }: Props) {
  const colorCls = STATUS_COLORS[run.status];
  const label = STATUS_LABELS[run.status];

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 space-y-3">
      <div className="flex items-center gap-3">
        <span
          className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold font-mono ${colorCls}`}
        >
          {label}
        </span>
        <span className="text-zinc-400 text-xs font-mono truncate">
          {run.run_id}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-4 text-xs font-mono">
        <div>
          <p className="text-zinc-500 uppercase tracking-wider mb-1">Created</p>
          <p className="text-zinc-300">{fmtTs(run.created_at)}</p>
        </div>
        <div>
          <p className="text-zinc-500 uppercase tracking-wider mb-1">Started</p>
          <p className="text-zinc-300">{fmtTs(run.started_at)}</p>
        </div>
        <div>
          <p className="text-zinc-500 uppercase tracking-wider mb-1">
            Completed
          </p>
          <p className="text-zinc-300">{fmtTs(run.completed_at)}</p>
        </div>
      </div>

      {run.error_message && (
        <p className="text-xs font-mono text-red-400 bg-red-950 rounded px-3 py-2 border border-red-900">
          {run.error_message}
        </p>
      )}

      <div className="text-xs font-mono text-zinc-500">
        seed={run.config.seed} · corpus={run.config.corpus_size} · suite=
        {run.config.suite_size}
      </div>
    </div>
  );
}
