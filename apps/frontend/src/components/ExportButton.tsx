"use client";

import { useState } from "react";
import { api } from "@/lib/api";

interface Props {
  runId: string;
}

export function ExportButton({ runId }: Props) {
  const [state, setState] = useState<
    "idle" | "loading" | "done" | "error"
  >("idle");
  const [path, setPath] = useState<string | null>(null);

  async function handleExport() {
    setState("loading");
    try {
      const res = await api.exportRun(runId);
      setPath(res.artifact_path);
      setState("done");
    } catch {
      setState("error");
    }
  }

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={handleExport}
        disabled={state === "loading"}
        className="rounded bg-zinc-700 hover:bg-zinc-600 disabled:opacity-50 px-4 py-2 text-sm font-semibold text-zinc-200 transition-colors"
      >
        {state === "loading" ? "Exporting…" : "Export JSON"}
      </button>
      {state === "done" && path && (
        <span className="text-xs font-mono text-emerald-400 truncate">
          Saved → {path}
        </span>
      )}
      {state === "error" && (
        <span className="text-xs font-mono text-red-400">Export failed.</span>
      )}
    </div>
  );
}
