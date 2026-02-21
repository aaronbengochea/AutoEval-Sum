/**
 * TypeScript types mirroring the backend Pydantic schemas.
 * Keep in sync with apps/backend/src/autoeval_sum/models/schemas.py and models/runs.py.
 */

export type RunStatus =
  | "queued"
  | "running"
  | "completed"
  | "completed_with_errors"
  | "failed";

export type FailureTag =
  | "missed_key_point"
  | "hallucinated_fact"
  | "unsupported_claim"
  | "verbosity_excess"
  | "over_compression"
  | "poor_structure"
  | "topic_drift"
  | "entity_error";

export type DifficultyTag = "easy" | "medium" | "hard";

export interface RunConfig {
  seed: number;
  corpus_size: number;
  suite_size: number;
}

export interface EvalCase {
  eval_id: string;
  doc_id: string;
  prompt_template: string;
  constraints: Record<string, unknown>;
  rubric_note: string;
  difficulty_tag: DifficultyTag;
  category_tag: string;
}

export interface SuiteMetrics {
  suite_id: string;
  avg_scores_by_dimension: Record<string, number>;
  aggregate_avg: number;
  pass_rate: number;
  failure_detection_rate: number;
  top_failure_modes: string[];
  worst_examples: EvalCase[];
}

// ── Run API responses ────────────────────────────────────────────────────────

export interface RunStartResponse {
  run_id: string;
  status: string;
  message: string;
}

export interface RunStatusResponse {
  run_id: string;
  status: RunStatus;
  config: RunConfig;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  metrics_v1: SuiteMetrics | null;
  metrics_v2: SuiteMetrics | null;
}

export interface CancelResponse {
  run_id: string;
  cancel_requested: boolean;
  message: string;
}

export interface RunResultsResponse {
  run_id: string;
  status: RunStatus;
  metrics_v1: SuiteMetrics | null;
  metrics_v2: SuiteMetrics | null;
  suites: Record<string, unknown>[];
}

export interface CompareRunSummary {
  run_id: string;
  status: RunStatus;
  completed_at: string | null;
  metrics_v1: SuiteMetrics | null;
  metrics_v2: SuiteMetrics | null;
}

export interface CompareLatestResponse {
  newer: CompareRunSummary;
  older: CompareRunSummary;
}

export interface ExportResponse {
  run_id: string;
  artifact_path: string;
}
