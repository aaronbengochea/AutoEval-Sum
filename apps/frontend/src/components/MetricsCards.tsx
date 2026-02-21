"use client";

import type { SuiteMetrics } from "@/lib/types";

interface CardProps {
  label: string;
  value: string;
  sub?: string;
  highlight?: boolean;
}

function StatCard({ label, value, sub, highlight }: CardProps) {
  return (
    <div
      className={`rounded-lg border p-4 ${
        highlight
          ? "border-emerald-700 bg-emerald-950"
          : "border-zinc-800 bg-zinc-900"
      }`}
    >
      <p className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-1">
        {label}
      </p>
      <p className="text-2xl font-bold font-mono text-zinc-100">{value}</p>
      {sub && <p className="text-xs font-mono text-zinc-500 mt-1">{sub}</p>}
    </div>
  );
}

interface SuiteCardSetProps {
  label: string;
  metrics: SuiteMetrics;
}

function SuiteCardSet({ label, metrics }: SuiteCardSetProps) {
  const dim = metrics.avg_scores_by_dimension;
  const pct = (n: number) => `${(n * 100).toFixed(1)}%`;
  const score = (n: number) => n.toFixed(2);

  return (
    <div className="space-y-3">
      <h3 className="text-xs font-mono font-semibold text-zinc-400 uppercase tracking-widest">
        {label}
      </h3>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard
          label="Pass rate"
          value={pct(metrics.pass_rate)}
          highlight={metrics.pass_rate >= 0.6}
        />
        <StatCard
          label="Aggregate avg"
          value={score(metrics.aggregate_avg)}
          sub="out of 5.0"
          highlight={metrics.aggregate_avg >= 3.5}
        />
        <StatCard
          label="Failure detection"
          value={pct(metrics.failure_detection_rate)}
        />
        <StatCard
          label="Coverage"
          value={score(dim.coverage ?? 0)}
          sub={`faithfulness ${score(dim.faithfulness ?? 0)}`}
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
      {metricsV1 && <SuiteCardSet label="V1 — Baseline Suite" metrics={metricsV1} />}
      {metricsV2 && <SuiteCardSet label="V2 — Improved Suite" metrics={metricsV2} />}
    </div>
  );
}
