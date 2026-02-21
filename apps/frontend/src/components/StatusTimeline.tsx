"use client";

import type { RunStatus, RunStatusResponse } from "@/lib/types";

const STATUS_CONFIG: Record<RunStatus, { color: string; dot: string; label: string; pulse?: boolean }> = {
  queued:                { color: "text-zinc-400 bg-zinc-800 border-zinc-700",      dot: "bg-zinc-500",   label: "Queued" },
  running:               { color: "text-blue-300 bg-blue-950 border-blue-800",      dot: "bg-blue-400",   label: "Running", pulse: true },
  completed:             { color: "text-emerald-300 bg-emerald-950 border-emerald-800", dot: "bg-emerald-400", label: "Completed" },
  completed_with_errors: { color: "text-amber-300 bg-amber-950 border-amber-800",   dot: "bg-amber-400",  label: "Completed (errors)" },
  failed:                { color: "text-red-300 bg-red-950 border-red-800",          dot: "bg-red-400",    label: "Failed" },
};

function fmtTs(ts: string | null): string {
  if (!ts) return "—";
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

interface Props {
  run: RunStatusResponse;
}

export function StatusTimeline({ run }: Props) {
  const cfg = STATUS_CONFIG[run.status];

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 space-y-4 backdrop-blur-sm">
      {/* Status badge + run ID */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold font-mono border ${cfg.color}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot} ${cfg.pulse ? "animate-pulse" : ""}`} />
          {cfg.label}
        </span>
        <span className="text-xs font-mono text-zinc-600 truncate">
          {run.run_id}
        </span>
      </div>

      {/* Timeline steps */}
      <div className="grid grid-cols-3 gap-6">
        {[
          { label: "Created",   value: fmtTs(run.created_at) },
          { label: "Started",   value: fmtTs(run.started_at) },
          { label: "Completed", value: fmtTs(run.completed_at) },
        ].map(({ label, value }) => (
          <div key={label}>
            <p className="text-xs font-mono text-zinc-600 uppercase tracking-wider mb-1">{label}</p>
            <p className="text-sm font-mono text-zinc-300">{value}</p>
          </div>
        ))}
      </div>

      {/* Config tags */}
      <div className="flex items-center gap-2 flex-wrap">
        {[
          `seed=${run.config.seed}`,
          `corpus=${run.config.corpus_size}`,
          `suite=${run.config.suite_size}`,
        ].map((tag) => (
          <span key={tag} className="text-xs font-mono text-zinc-500 bg-zinc-800 rounded px-2 py-0.5 border border-zinc-700/50">
            {tag}
          </span>
        ))}
      </div>

      {/* Error message */}
      {run.error_message && (
        <div className="rounded-lg bg-red-950/50 border border-red-900 px-4 py-3">
          <p className="text-xs font-mono text-red-400">{run.error_message}</p>
        </div>
      )}
    </div>
  );
}
