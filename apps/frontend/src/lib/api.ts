/**
 * Typed API client for the AutoEval-Sum backend.
 * All requests go through the /api/backend proxy to avoid CORS issues.
 */

import axios from "axios";
import type {
  CancelResponse,
  CompareLatestResponse,
  ExportResponse,
  RunResultsResponse,
  RunStartResponse,
  RunStatusResponse,
} from "./types";

const client = axios.create({
  baseURL: "/api/backend",
  headers: { "Content-Type": "application/json" },
});

export interface StartRunParams {
  seed?: number;
  corpus_size?: number;
  suite_size?: number;
}

export const api = {
  startRun: (params: StartRunParams = {}) =>
    client
      .post<RunStartResponse>("/api/v1/runs/start", params)
      .then((r) => r.data),

  getRunStatus: (runId: string) =>
    client
      .get<RunStatusResponse>(`/api/v1/runs/${runId}`)
      .then((r) => r.data),

  cancelRun: (runId: string) =>
    client
      .post<CancelResponse>(`/api/v1/runs/${runId}/cancel`)
      .then((r) => r.data),

  getRunResults: (runId: string) =>
    client
      .get<RunResultsResponse>(`/api/v1/runs/${runId}/results`)
      .then((r) => r.data),

  compareLatest: () =>
    client
      .get<CompareLatestResponse>("/api/v1/runs/compare/latest")
      .then((r) => r.data),

  exportRun: (runId: string) =>
    client
      .get<ExportResponse>(`/api/v1/runs/${runId}/export`)
      .then((r) => r.data),
};
