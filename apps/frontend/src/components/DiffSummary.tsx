"use client";

import type { SuiteMetrics } from "@/lib/types";

function delta(v1: number, v2: number): { text: string; positive: boolean } {
  const d = v2 - v1;
  const sign = d >= 0 ? "+" : "";
  return { text: `${sign}${d.toFixed(3)}`, positive: d >= 0 };
}

function pctDelta(v1: number, v2: number) {
  const d = (v2 - v1) * 100;
  const sign = d >= 0 ? "+" : "";
  return { text: `${sign}${d.toFixed(1)}pp`, positive: d >= 0 };
}

interface RowProps {
  label: string;
  v1: string;
  v2: string;
  diff: { text: string; positive: boolean };
}

function Row({ label, v1, v2, diff }: RowProps) {
  return (
    <tr className="border-b border-zinc-800/50">
      <td className="py-2 pr-6 text-zinc-400 font-mono text-xs">{label}</td>
      <td className="py-2 pr-6 text-zinc-300 font-mono text-xs text-right">{v1}</td>
      <td className="py-2 pr-6 text-zinc-300 font-mono text-xs text-right">{v2}</td>
      <td
        className={`py-2 font-mono text-xs font-semibold text-right ${
          diff.positive ? "text-emerald-400" : "text-red-400"
        }`}
      >
        {diff.text}
      </td>
    </tr>
  );
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

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 space-y-3">
      <h3 className="text-xs font-mono font-semibold text-zinc-400 uppercase tracking-widest">
        V1 → V2 Improvement Diff
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-zinc-700">
              <th className="text-left py-2 pr-6 text-zinc-500 font-mono text-xs">
                Metric
              </th>
              <th className="text-right py-2 pr-6 text-zinc-500 font-mono text-xs">
                V1
              </th>
              <th className="text-right py-2 pr-6 text-zinc-500 font-mono text-xs">
                V2
              </th>
              <th className="text-right py-2 text-zinc-500 font-mono text-xs">
                Delta
              </th>
            </tr>
          </thead>
          <tbody>
            <Row
              label="Pass Rate"
              v1={pct(metricsV1.pass_rate)}
              v2={pct(metricsV2.pass_rate)}
              diff={pctDelta(metricsV1.pass_rate, metricsV2.pass_rate)}
            />
            <Row
              label="Aggregate Avg"
              v1={sc(metricsV1.aggregate_avg)}
              v2={sc(metricsV2.aggregate_avg)}
              diff={delta(metricsV1.aggregate_avg, metricsV2.aggregate_avg)}
            />
            <Row
              label="Failure Detection"
              v1={pct(metricsV1.failure_detection_rate)}
              v2={pct(metricsV2.failure_detection_rate)}
              diff={pctDelta(
                metricsV1.failure_detection_rate,
                metricsV2.failure_detection_rate
              )}
            />
            {["coverage", "faithfulness", "conciseness", "structure"].map((dim) => (
              <Row
                key={dim}
                label={dim.charAt(0).toUpperCase() + dim.slice(1)}
                v1={sc(dim1[dim] ?? 0)}
                v2={sc(dim2[dim] ?? 0)}
                diff={delta(dim1[dim] ?? 0, dim2[dim] ?? 0)}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
