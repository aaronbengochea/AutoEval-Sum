"use client";

import type { SuiteMetrics } from "@/lib/types";

const DIFFICULTY_STYLE = {
  easy:   "text-emerald-400 bg-emerald-950/50 border-emerald-800/50",
  medium: "text-amber-400 bg-amber-950/50 border-amber-800/50",
  hard:   "text-red-400 bg-red-950/50 border-red-800/50",
};

interface Props {
  metricsV1: SuiteMetrics | null;
  metricsV2: SuiteMetrics | null;
}

function CasesTable({ metrics, version }: { metrics: SuiteMetrics; version: "v1" | "v2" }) {
  if (metrics.worst_examples.length === 0) {
    return <p className="text-xs font-mono text-zinc-600 py-3">No worst examples recorded.</p>;
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 mb-2">
        <span className={`text-xs font-mono font-bold rounded px-2 py-0.5 ${
          version === "v2"
            ? "bg-indigo-950 text-indigo-400 border border-indigo-800"
            : "bg-zinc-800 text-zinc-400 border border-zinc-700"
        }`}>
          {version.toUpperCase()}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-zinc-800">
              {["Eval ID", "Difficulty", "Category", "Doc ID"].map((h) => (
                <th key={h} className="text-left pb-2 pr-6 text-xs font-mono font-medium text-zinc-600 uppercase tracking-wider">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/40">
            {metrics.worst_examples.map((c) => (
              <tr key={c.eval_id} className="hover:bg-zinc-800/20 transition-colors">
                <td className="py-2.5 pr-6 text-xs font-mono text-zinc-300">{c.eval_id}</td>
                <td className="py-2.5 pr-6">
                  <span className={`text-xs font-mono rounded-full px-2 py-0.5 border ${DIFFICULTY_STYLE[c.difficulty_tag]}`}>
                    {c.difficulty_tag}
                  </span>
                </td>
                <td className="py-2.5 pr-6 text-xs font-mono text-zinc-400">{c.category_tag}</td>
                <td className="py-2.5 text-xs font-mono text-zinc-600 truncate max-w-xs">{c.doc_id}</td>
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
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 space-y-6 backdrop-blur-sm">
      {metricsV1 && <CasesTable metrics={metricsV1} version="v1" />}
      {metricsV2 && <CasesTable metrics={metricsV2} version="v2" />}
    </div>
  );
}
