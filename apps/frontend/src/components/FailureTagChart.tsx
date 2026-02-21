"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { SuiteMetrics, FailureTag } from "@/lib/types";

const ALL_TAGS: FailureTag[] = [
  "missed_key_point",
  "hallucinated_fact",
  "unsupported_claim",
  "verbosity_excess",
  "over_compression",
  "poor_structure",
  "topic_drift",
  "entity_error",
];

const TAG_LABELS: Record<FailureTag, string> = {
  missed_key_point: "Missed Key Point",
  hallucinated_fact: "Hallucination",
  unsupported_claim: "Unsupported Claim",
  verbosity_excess: "Verbosity",
  over_compression: "Over-Compression",
  poor_structure: "Poor Structure",
  topic_drift: "Topic Drift",
  entity_error: "Entity Error",
};

function presence(modes: string[], tag: FailureTag): number {
  return modes.includes(tag) ? 1 : 0;
}

interface Props {
  metricsV1: SuiteMetrics | null;
  metricsV2: SuiteMetrics | null;
}

export function FailureTagChart({ metricsV1, metricsV2 }: Props) {
  if (!metricsV1 && !metricsV2) return null;

  const data = ALL_TAGS.map((tag) => ({
    tag: TAG_LABELS[tag],
    V1: metricsV1 ? presence(metricsV1.top_failure_modes, tag) : 0,
    V2: metricsV2 ? presence(metricsV2.top_failure_modes, tag) : 0,
  }));

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 space-y-3">
      <h3 className="text-xs font-mono font-semibold text-zinc-400 uppercase tracking-widest">
        Top Failure Modes
      </h3>
      <p className="text-xs text-zinc-600 font-mono">
        1 = appears in top failure modes · 0 = not present
      </p>
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 8, left: -24, bottom: 60 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
            <XAxis
              dataKey="tag"
              tick={{ fill: "#71717a", fontSize: 10, fontFamily: "monospace" }}
              angle={-35}
              textAnchor="end"
              interval={0}
            />
            <YAxis
              tick={{ fill: "#71717a", fontSize: 10 }}
              domain={[0, 1]}
              ticks={[0, 1]}
            />
            <Tooltip
              contentStyle={{
                background: "#18181b",
                border: "1px solid #3f3f46",
                borderRadius: 6,
                fontFamily: "monospace",
                fontSize: 12,
              }}
            />
            <Legend
              wrapperStyle={{ fontSize: 12, fontFamily: "monospace", paddingTop: 8 }}
            />
            <Bar dataKey="V1" fill="#3f82f6" radius={[2, 2, 0, 0]}>
              {data.map((_, i) => (
                <Cell key={i} fill={data[i].V1 ? "#3f82f6" : "#1e3a5f"} />
              ))}
            </Bar>
            <Bar dataKey="V2" fill="#10b981" radius={[2, 2, 0, 0]}>
              {data.map((_, i) => (
                <Cell key={i} fill={data[i].V2 ? "#10b981" : "#052e16"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
