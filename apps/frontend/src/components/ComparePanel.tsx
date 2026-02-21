"use client";

import { useCompareLatest } from "@/hooks/useCompareLatest";
import type { CompareRunSummary } from "@/lib/types";

function pct(n: number) {
  return `${(n * 100).toFixed(1)}%`;
}
function sc(n: number) {
  return n.toFixed(3);
}

function RunColumn({
  run,
  label,
}: {
  run: CompareRunSummary;
  label: string;
}) {
  const v2 = run.metrics_v2;

  return (
    <div className="flex-1 space-y-3">
      <div>
        <p className="text-xs font-mono text-zinc-500 uppercase tracking-widest mb-1">
          {label}
        </p>
        <p className="text-xs font-mono text-zinc-300 truncate">{run.run_id}</p>
        {run.completed_at && (
          <p className="text-xs font-mono text-zinc-600">
            {new Date(run.completed_at).toLocaleString()}
          </p>
        )}
      </div>

      {v2 ? (
        <div className="space-y-2">
          <Stat label="V2 Pass Rate" value={pct(v2.pass_rate)} />
          <Stat label="V2 Aggregate" value={sc(v2.aggregate_avg)} />
          <Stat
            label="V2 Failure Detection"
            value={pct(v2.failure_detection_rate)}
          />
          {v2.top_failure_modes.length > 0 && (
            <div>
              <p className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-1">
                Top Modes
              </p>
              <div className="flex flex-wrap gap-1">
                {v2.top_failure_modes.map((m) => (
                  <span
                    key={m}
                    className="text-xs font-mono bg-zinc-800 text-zinc-400 rounded px-2 py-0.5"
                  >
                    {m.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <p className="text-xs font-mono text-zinc-600">No V2 metrics.</p>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-mono text-zinc-500 uppercase tracking-wider">
        {label}
      </p>
      <p className="text-sm font-mono font-semibold text-zinc-200">{value}</p>
    </div>
  );
}

export function ComparePanel() {
  const { data, isLoading, isError } = useCompareLatest();

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 space-y-4">
      <h3 className="text-xs font-mono font-semibold text-zinc-400 uppercase tracking-widest">
        Latest Two Runs — Comparison
      </h3>

      {isLoading && (
        <p className="text-xs font-mono text-zinc-600">Loading…</p>
      )}

      {isError && (
        <p className="text-xs font-mono text-zinc-600">
          Fewer than two completed runs — comparison unavailable.
        </p>
      )}

      {data && (
        <div className="flex gap-6 divide-x divide-zinc-800">
          <RunColumn run={data.newer} label="Newer" />
          <div className="pl-6 flex-1">
            <RunColumn run={data.older} label="Older" />
          </div>
        </div>
      )}
    </div>
  );
}
