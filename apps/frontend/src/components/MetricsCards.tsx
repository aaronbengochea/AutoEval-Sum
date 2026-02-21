"use client";

import type { SuiteMetrics } from "@/lib/types";

interface StatCardProps {
  label: string;
  value: string;
  sub?: string;
  positive?: boolean;
}

function StatCard({ label, value, sub, positive }: StatCardProps) {
  return (
    <div className={`rounded-xl border p-4 transition-colors ${
      positive === true
        ? "border-emerald-800/60 bg-emerald-950/30"
        : positive === false
        ? "border-red-800/60 bg-red-950/20"
        : "border-zinc-800 bg-zinc-900/60"
    }`}>
      <p className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-2">{label}</p>
      <p className="text-2xl font-bold font-mono text-zinc-100 tabular-nums">{value}</p>
      {sub && <p className="text-xs font-mono text-zinc-600 mt-1">{sub}</p>}
    </div>
  );
}

function SuiteSection({ label, version, metrics }: { label: string; version: "v1" | "v2"; metrics: SuiteMetrics }) {
  const dim = metrics.avg_scores_by_dimension;
  const pct = (n: number) => `${(n * 100).toFixed(1)}%`;
  const sc = (n: number) => n.toFixed(2);
  const isV2 = version === "v2";

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className={`text-xs font-mono font-bold rounded px-2 py-0.5 ${
          isV2
            ? "bg-indigo-950 text-indigo-400 border border-indigo-800"
            : "bg-zinc-800 text-zinc-400 border border-zinc-700"
        }`}>
          {version.toUpperCase()}
        </span>
        <span className="text-xs font-mono text-zinc-500">{label}</span>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard
          label="Pass Rate"
          value={pct(metrics.pass_rate)}
          positive={metrics.pass_rate >= 0.6}
        />
        <StatCard
          label="Aggregate Avg"
          value={sc(metrics.aggregate_avg)}
          sub="out of 5.0"
          positive={metrics.aggregate_avg >= 3.5}
        />
        <StatCard
          label="Failure Detection"
          value={pct(metrics.failure_detection_rate)}
        />
        <StatCard
          label="Coverage"
          value={sc(dim.coverage ?? 0)}
          sub={`faithfulness ${sc(dim.faithfulness ?? 0)}`}
        />
      </div>
    </div>
  );
}

interface Props {
  metricsV1: SuiteMetrics | null;
  metricsV2: SuiteMetrics | null;
}

export function MetricsCards({ metricsV1, metricsV2 }: Props) {
  return (
    <div className="space-y-6">
      {metricsV1 && <SuiteSection label="Baseline Suite" version="v1" metrics={metricsV1} />}
      {metricsV2 && <SuiteSection label="Improved Suite"  version="v2" metrics={metricsV2} />}
    </div>
  );
}
