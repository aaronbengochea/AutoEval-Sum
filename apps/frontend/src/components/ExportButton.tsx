"use client";

import { useState } from "react";
import { api } from "@/lib/api";

interface Props {
  runId: string;
}

export function ExportButton({ runId }: Props) {
  const [state, setState] = useState<"idle" | "loading" | "done" | "error">("idle");
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
        disabled={state === "loading" || state === "done"}
        className="inline-flex items-center gap-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 text-sm font-semibold text-zinc-300 transition-colors"
      >
        {state === "loading" ? (
          <>
            <SpinIcon /> Exporting…
          </>
        ) : state === "done" ? (
          <>
            <CheckIcon /> Exported
          </>
        ) : (
          <>
            <DownloadIcon /> Export JSON
          </>
        )}
      </button>

      {state === "done" && path && (
        <span className="text-xs font-mono text-emerald-400 truncate max-w-sm">
          → {path}
        </span>
      )}
      {state === "error" && (
        <span className="text-xs font-mono text-red-400">Export failed.</span>
      )}
    </div>
  );
}

function DownloadIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  );
}

function SpinIcon() {
  return (
    <svg className="animate-spin w-3.5 h-3.5" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}
