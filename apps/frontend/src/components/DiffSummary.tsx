"use client";

import type { SuiteMetrics } from "@/lib/types";

function delta(v1: number, v2: number) {
  const d = v2 - v1;
  return { text: `${d >= 0 ? "+" : ""}${d.toFixed(3)}`, positive: d >= 0, zero: Math.abs(d) < 0.001 };
}

function pctDelta(v1: number, v2: number) {
  const d = (v2 - v1) * 100;
  return { text: `${d >= 0 ? "+" : ""}${d.toFixed(1)}pp`, positive: d >= 0, zero: Math.abs(d) < 0.01 };
}

interface Props {
  metricsV1: SuiteMetrics;
  metricsV2: SuiteMetrics;
}

export function DiffSummary({ metricsV1, metricsV2 }: Props) {
  const dim1 = metricsV1.avg_scores_by_dimension;
  const dim2 = metricsV2.avg_scores_by_dimension;
  const pct = (n: number) => `${(n * 100).toFixed(1)}%`;
  const sc = (n: number) => n.toFixed(3);

  const rows = [
    { label: "Pass Rate",         v1: pct(metricsV1.pass_rate),              v2: pct(metricsV2.pass_rate),              diff: pctDelta(metricsV1.pass_rate, metricsV2.pass_rate) },
    { label: "Aggregate Avg",     v1: sc(metricsV1.aggregate_avg),           v2: sc(metricsV2.aggregate_avg),           diff: delta(metricsV1.aggregate_avg, metricsV2.aggregate_avg) },
    { label: "Failure Detection", v1: pct(metricsV1.failure_detection_rate), v2: pct(metricsV2.failure_detection_rate), diff: pctDelta(metricsV1.failure_detection_rate, metricsV2.failure_detection_rate) },
    ...["coverage", "faithfulness", "conciseness", "structure"].map((dim) => ({
      label: dim.charAt(0).toUpperCase() + dim.slice(1),
      v1: sc(dim1[dim] ?? 0),
      v2: sc(dim2[dim] ?? 0),
      diff: delta(dim1[dim] ?? 0, dim2[dim] ?? 0),
    })),
  ];

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 overflow-hidden backdrop-blur-sm">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-zinc-800 bg-zinc-900/80">
              <th className="text-left px-5 py-3 text-xs font-mono font-medium text-zinc-500 uppercase tracking-wider">Metric</th>
              <th className="text-right px-5 py-3 text-xs font-mono font-medium text-zinc-500 uppercase tracking-wider">V1</th>
              <th className="text-right px-5 py-3 text-xs font-mono font-medium text-zinc-500 uppercase tracking-wider">V2</th>
              <th className="text-right px-5 py-3 text-xs font-mono font-medium text-zinc-500 uppercase tracking-wider">Delta</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/50">
            {rows.map(({ label, v1, v2, diff }) => (
              <tr key={label} className="hover:bg-zinc-800/20 transition-colors">
                <td className="px-5 py-3 text-sm font-mono text-zinc-400">{label}</td>
                <td className="px-5 py-3 text-sm font-mono text-zinc-400 text-right tabular-nums">{v1}</td>
                <td className="px-5 py-3 text-sm font-mono text-zinc-200 text-right tabular-nums font-medium">{v2}</td>
                <td className={`px-5 py-3 text-sm font-mono font-bold text-right tabular-nums ${
                  diff.zero ? "text-zinc-600" : diff.positive ? "text-emerald-400" : "text-red-400"
                }`}>
                  {diff.text}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
