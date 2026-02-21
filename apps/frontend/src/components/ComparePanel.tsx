"use client";

import { useCompareLatest } from "@/hooks/useCompareLatest";
import type { CompareRunSummary } from "@/lib/types";

function pct(n: number) { return `${(n * 100).toFixed(1)}%`; }
function sc(n: number) { return n.toFixed(3); }

function RunColumn({ run, label, isNewer }: { run: CompareRunSummary; label: string; isNewer: boolean }) {
  const v2 = run.metrics_v2;

  return (
    <div className="flex-1 space-y-4">
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-mono font-bold rounded px-2 py-0.5 border ${
            isNewer
              ? "bg-indigo-950 text-indigo-400 border-indigo-800"
              : "bg-zinc-800 text-zinc-500 border-zinc-700"
          }`}>
            {label}
          </span>
          <span className={`w-1.5 h-1.5 rounded-full ${
            run.status === "completed" ? "bg-emerald-400" :
            run.status === "completed_with_errors" ? "bg-amber-400" : "bg-red-400"
          }`} />
        </div>
        <p className="text-xs font-mono text-zinc-600 truncate">{run.run_id}</p>
        {run.completed_at && (
          <p className="text-xs font-mono text-zinc-700">
            {new Date(run.completed_at).toLocaleString()}
          </p>
        )}
      </div>

      {v2 ? (
        <div className="space-y-3">
          {[
            { label: "V2 Pass Rate",        value: pct(v2.pass_rate) },
            { label: "V2 Aggregate",        value: sc(v2.aggregate_avg) },
            { label: "V2 Failure Detection", value: pct(v2.failure_detection_rate) },
          ].map(({ label, value }) => (
            <div key={label}>
              <p className="text-xs font-mono text-zinc-600 uppercase tracking-wider mb-0.5">{label}</p>
              <p className="text-sm font-mono font-semibold text-zinc-200 tabular-nums">{value}</p>
            </div>
          ))}

          {v2.top_failure_modes.length > 0 && (
            <div>
              <p className="text-xs font-mono text-zinc-600 uppercase tracking-wider mb-1.5">Top Failure Modes</p>
              <div className="flex flex-wrap gap-1">
                {v2.top_failure_modes.map((m) => (
                  <span key={m} className="text-xs font-mono bg-zinc-800 text-zinc-400 rounded px-2 py-0.5 border border-zinc-700/50">
                    {m.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <p className="text-xs font-mono text-zinc-700">No V2 metrics yet.</p>
      )}
    </div>
  );
}

export function ComparePanel() {
  const { data, isLoading, isError } = useCompareLatest();

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 backdrop-blur-sm">
      {isLoading && (
        <p className="text-xs font-mono text-zinc-600">Loading…</p>
      )}

      {isError && (
        <div className="text-center py-6">
          <p className="text-xs font-mono text-zinc-700">
            Fewer than two completed runs — comparison unavailable after your first run completes.
          </p>
        </div>
      )}

      {data && (
        <div className="grid grid-cols-2 divide-x divide-zinc-800">
          <div className="pr-6">
            <RunColumn run={data.newer} label="Newer" isNewer={true} />
          </div>
          <div className="pl-6">
            <RunColumn run={data.older} label="Older" isNewer={false} />
          </div>
        </div>
      )}
    </div>
  );
}
