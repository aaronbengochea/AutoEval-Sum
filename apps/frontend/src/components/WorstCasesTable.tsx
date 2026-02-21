"use client";

import type { SuiteMetrics } from "@/lib/types";

const DIFFICULTY_COLORS = {
  easy: "text-emerald-400",
  medium: "text-amber-400",
  hard: "text-red-400",
};

interface Props {
  metricsV1: SuiteMetrics | null;
  metricsV2: SuiteMetrics | null;
}

function CasesTable({ metrics, label }: { metrics: SuiteMetrics; label: string }) {
  const examples = metrics.worst_examples;
  if (examples.length === 0) {
    return (
      <div className="text-xs font-mono text-zinc-600 py-4 text-center">
        No worst examples recorded.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <h4 className="text-xs font-mono text-zinc-500 uppercase tracking-widest">
        {label}
      </h4>
      <div className="overflow-x-auto">
        <table className="w-full text-xs font-mono">
          <thead>
            <tr className="border-b border-zinc-800">
              <th className="text-left py-2 pr-4 text-zinc-500 font-medium">
                Eval ID
              </th>
              <th className="text-left py-2 pr-4 text-zinc-500 font-medium">
                Difficulty
              </th>
              <th className="text-left py-2 pr-4 text-zinc-500 font-medium">
                Category
              </th>
              <th className="text-left py-2 text-zinc-500 font-medium">
                Doc ID
              </th>
            </tr>
          </thead>
          <tbody>
            {examples.map((c) => (
              <tr key={c.eval_id} className="border-b border-zinc-800/50">
                <td className="py-2 pr-4 text-zinc-300">{c.eval_id}</td>
                <td
                  className={`py-2 pr-4 ${DIFFICULTY_COLORS[c.difficulty_tag]}`}
                >
                  {c.difficulty_tag}
                </td>
                <td className="py-2 pr-4 text-zinc-400">{c.category_tag}</td>
                <td className="py-2 text-zinc-600 truncate max-w-xs">
                  {c.doc_id}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function WorstCasesTable({ metricsV1, metricsV2 }: Props) {
  if (!metricsV1 && !metricsV2) return null;

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 space-y-5">
      <h3 className="text-xs font-mono font-semibold text-zinc-400 uppercase tracking-widest">
        Worst Examples (≤ 5 per suite)
      </h3>
      {metricsV1 && <CasesTable metrics={metricsV1} label="V1" />}
      {metricsV2 && <CasesTable metrics={metricsV2} label="V2" />}
    </div>
  );
}
