# AutoEval-Sum v1 — Phased Implementation Plan

> This document drives execution. Each phase has explicit subphases, concrete outputs, and exit criteria. Work subphase-by-subphase, verify exit criteria before advancing. See `holisticPlan.md` for full architectural context.

---

## Phase 0 — Project Foundation

### [X] Subphase 0.1: Create monorepo structure
- **Action:** Create `apps/frontend`, `apps/backend`, `infra`, `artifacts/exports`, `data` directories.
- **Output:** Directories, `.gitignore` covering dataset/cache/artifacts.
- **Exit criteria:** Clean repo layout with no ambiguity.

### [X] Subphase 0.2: Initialize tooling
- **Action:** Set up `uv` for backend, `pnpm` for frontend, root `Makefile`.
- **Output:** `pyproject.toml`, `package.json`, root `Makefile`.
- **Exit criteria:** One-command install/build works.

### [X] Subphase 0.3: Add typed config scaffolding
- **Action:** Create backend settings model, frontend env contract, `.env.example`.
- **Output:** Backend settings model, frontend env contract, `.env.example`.
- **Exit criteria:** Startup fails fast on missing required vars.

### [X] Subphase 0.4: Add Docker Compose baseline services
- **Action:** Write `docker-compose.yml` with `frontend`, `backend`, `dynamodb-local`, shared volumes.
- **Output:** `docker-compose.yml`.
- **Exit criteria:** `docker compose up` boots all services.

---

## Phase 1 — Infra Bootstrap (Idempotent)

### [X] Subphase 1.1: Implement DynamoDB init script
- **Action:** Write create-if-missing script for 4 tables: `AutoEvalRuns`, `Documents`, `EvalSuites`, `EvalResults`.
- **Output:** Init script.
- **Exit criteria:** Script can run repeatedly without destructive behavior.

### [X] Subphase 1.2: Implement Pinecone init script
- **Action:** Write script creating project-named index and namespaces `eval_prompts`, `failures`.
- **Output:** Pinecone init script.
- **Exit criteria:** Repeated runs are no-op safe.

### [X] Subphase 1.3: Wire init scripts into container startup flow
- **Action:** Add startup sequence that verifies infra readiness before app runs.
- **Output:** Updated compose/entrypoint with ordered startup.
- **Exit criteria:** Fresh machine boot requires no manual table/index setup.

### [X] Subphase 1.4: Add health checks
- **Action:** Implement backend readiness checks for DynamoDB + Pinecone connectivity.
- **Output:** Health check endpoints/probes.
- **Exit criteria:** Compose health shows healthy only when dependencies are ready.

---

## Phase 2 — Dataset Ingestion and Document Catalog

### [X] Subphase 2.1: Implement MSMARCO fetcher
- **Action:** Build loader for `microsoft/ms_marco` docs split with local cache volume.
- **Output:** Fetcher module with cache layer.
- **Exit criteria:** Repeat runs reuse cache; no git-tracked dataset artifacts.

### [X] Subphase 2.2: Implement deterministic filtering and sampling
- **Action:** Apply English + >=500 words filters, seeded random sample.
- **Output:** Filter/sample pipeline.
- **Exit criteria:** Same seed reproduces same doc set.

### [X] Subphase 2.3: Implement enrichment pipeline
- **Action:** Add category classification (LLM), token counting via Gemini `count_tokens`, entity density via spaCy `en_core_web_sm`, difficulty tagging.
- **Output:** Enrichment pipeline with per-doc metadata.
- **Exit criteria:** Each doc has stable metadata for suite balancing.

### [X] Subphase 2.4: Persist doc metadata
- **Action:** Write `Documents` records with content path, stats, category, difficulty signals.
- **Output:** Populated `Documents` DynamoDB table.
- **Exit criteria:** Ingest endpoint returns accepted count and metadata is queryable.

---

## Phase 3 — Agent Contracts and Prompt Assets

### [X] Subphase 3.1: Define strict Pydantic schemas for all agent I/O
- **Action:** Implement `SummaryStructured`, `EvalCase`, `JudgeCaseResult`, `SuiteMetrics`, `CurriculumOutput`.
- **Output:** Pydantic models with validation.
- **Exit criteria:** Schema validation catches malformed model output.

### [X] Subphase 3.2: Add versioned prompt files
- **Action:** Create prompt files for summarizer, eval author, judge, curriculum agents, plus global rubric definition.
- **Output:** Prompt asset files, diffable and decoupled from code.
- **Exit criteria:** Prompts are diffable and decoupled from code.

### [X] Subphase 3.3: Implement Summarizer Agent
- **Action:** Gemini call producing `{ title, key_points[5], abstract<=120 words }` with bullet caps enforced.
- **Output:** Summarizer agent module.
- **Exit criteria:** Always returns parseable structured JSON or explicit error.

### [X] Subphase 3.4: Implement Eval Author + Judge + Curriculum Agents
- **Action:** Build strict JSON pipelines for all three agents — hallucination auto-fail, fixed 8-tag taxonomy, concise rationale/evidence constraints.
- **Output:** Three agent modules.
- **Exit criteria:** Deterministic agent outputs at temperature 0.

---

## Phase 4 — LangGraph Runtime and Run Control

### [X] Subphase 4.1: Implement run queue and status model
- **Action:** Build single active run + FIFO queue with statuses `queued / running / completed / completed_with_errors / failed`.
- **Output:** Queue and status management layer.
- **Exit criteria:** Concurrent starts are serialized safely.

### [X] Subphase 4.2: Implement graph nodes and edges
- **Action:** Wire full node flow: `load_docs → init_run → eval_author_v1 → execute_v1 → judge_v1 → curriculum_v2 → execute_v2 → judge_v2 → finalize`.
- **Output:** LangGraph graph definition.
- **Exit criteria:** One run executes full autonomous v1→v2 loop.

### [X] Subphase 4.3: Implement execution policies
- **Action:** Add 4-worker bounded parallelism, 3-retry exponential backoff with jitter, 300k token cap, graceful partial finalization.
- **Output:** Execution policy layer.
- **Exit criteria:** Transient failures don't crash whole run.

### [X] Subphase 4.4: Implement cancellation and restart semantics
- **Action:** Soft cancel at case boundaries; restart marks in-progress run as failed.
- **Output:** Cancel/restart handlers.
- **Exit criteria:** Run state is always consistent and auditable.

---

## Phase 5 — Persistence + Pinecone Memory Integration

### [X] Subphase 5.1: Implement DynamoDB repositories
- **Action:** Build CRUD layer for runs, suites, results, events with UTC ISO timestamps.
- **Output:** Repository modules for all 4 tables.
- **Exit criteria:** All orchestration state persisted with UTC ISO timestamps.

### [X] Subphase 5.2: Implement Pinecone embedding/upsert/query
- **Action:** Embed via `text-embedding-004`, upsert to namespaces with full metadata.
- **Output:** Pinecone client wrapper.
- **Exit criteria:** Vector writes/queries succeed and are traceable to run/suite/eval IDs.

### [X] Subphase 5.3: Implement dedup logic
- **Action:** Reject candidate eval when cosine similarity >= 0.90 against `eval_prompts` namespace.
- **Output:** Dedup check function.
- **Exit criteria:** Curriculum avoids near-duplicate tests.

### [X] Subphase 5.4: Implement failure memory usage
- **Action:** Store/retrieve failure exemplars for targeted v2 generation.
- **Output:** Failure memory read/write paths integrated into curriculum agent.
- **Exit criteria:** Curriculum references prior failure modes in improvement plan.

---

## Phase 6 — FastAPI Public API Layer

### [X] Subphase 6.1: Implement ingestion endpoints
- **Action:** Build `POST /ingestion/prepare` and `GET /ingestion/status`.
- **Output:** Ingestion router.
- **Exit criteria:** Ingestion can be triggered on demand with cached reuse.

### [X] Subphase 6.2: Implement run lifecycle endpoints
- **Action:** Build `POST /runs/start`, `GET /runs/{id}`, `POST /runs/{id}/cancel`, `GET /runs/{id}/results`.
- **Output:** Runs router.
- **Exit criteria:** Frontend can fully control and monitor runs.

### [X] Subphase 6.3: Implement comparison/export endpoints
- **Action:** Build `GET /runs/compare/latest` and `GET /runs/{id}/export` writing to `artifacts/exports/`.
- **Output:** Comparison and export routes.
- **Exit criteria:** JSON artifact export works.

### [X] Subphase 6.4: Publish OpenAPI docs and error contracts
- **Action:** Ensure all routes have typed request/response models surfaced in FastAPI default docs.
- **Output:** Self-documenting OpenAPI spec.
- **Exit criteria:** API contracts are self-documenting.

---

## Phase 7 — Frontend Dashboard (Next.js)

### [X] Subphase 7.1: Scaffold app shell and data layer
- **Action:** Set up Tailwind UI shell, TanStack Query, backend proxy routes.
- **Output:** App shell with working API client.
- **Exit criteria:** Polling and API calls work without browser CORS issues.

### [X] Subphase 7.2: Build run controls and status timeline
- **Action:** Implement manual run trigger, cancel action, live status transitions.
- **Output:** Run control panel and status timeline component.
- **Exit criteria:** User can start/monitor/stop runs from UI.

### [X] Subphase 7.3: Build results panels
- **Action:** Build metrics cards, failure-tag chart (Recharts), worst 5 cases table, v1/v2 diff summary.
- **Output:** Results section components.
- **Exit criteria:** Technical audience can see improvement narrative directly.

### Subphase 7.4: Build historical comparison and export actions
- **Action:** Add current vs most recent completed run comparison panel and export button.
- **Output:** Comparison panel and export action.
- **Exit criteria:** One-click comparison and artifact retrieval works.

---

## Phase 8 — Testing and CI

### Subphase 8.1: Unit tests
- **Action:** Cover scoring math, pass/fail rules, taxonomy handling, difficulty heuristics, dedup threshold.
- **Output:** Unit test suite.
- **Exit criteria:** Core business logic is deterministic and covered.

### Subphase 8.2: API contract tests
- **Action:** Validate request/response schemas and run status transitions.
- **Output:** Contract test suite.
- **Exit criteria:** API remains stable for frontend and automation.

### Subphase 8.3: Integration tests with mocked externals
- **Action:** End-to-end run flow with mocked Gemini/Pinecone and local DynamoDB fixtures.
- **Output:** Integration test suite.
- **Exit criteria:** Full loop passes in CI without external keys.

### Subphase 8.4: Optional live smoke test
- **Action:** Reduced real-service run profile with actual Gemini/Pinecone/local DynamoDB.
- **Output:** Smoke test config and script.
- **Exit criteria:** Confirms real-key integration path before demo.

---

## Phase 9 — Demo Readiness and Runbook

### Subphase 9.1: Create operator runbook
- **Action:** Document exact startup commands, env setup, and troubleshooting paths.
- **Output:** `RUNBOOK.md`.
- **Exit criteria:** Another engineer can run demo from scratch.

### Subphase 9.2: Execute canonical demo run
- **Action:** Run default config (`seed=42`, `corpus=150`, `suite=20`) and save export artifact.
- **Output:** Saved export artifact in `artifacts/exports/`.
- **Exit criteria:** v1 and v2 both present with complete metrics.

### Subphase 9.3: Validate KPI story
- **Action:** Document failure detection delta and unique failure-tag coverage delta between v1 and v2.
- **Output:** KPI summary document.
- **Exit criteria:** Objective "suite improved" evidence is reproducible.

### Subphase 9.4: Freeze v1 release tag
- **Action:** Tag commit and pin prompt/config versions.
- **Output:** Git release tag.
- **Exit criteria:** Demo state is reproducible and stable.

---

## Stable Interfaces (Must Not Change Without Explicit Decision)

| Interface | Value |
|---|---|
| REST endpoints | `/ingestion/prepare`, `/ingestion/status`, `/runs/start`, `/runs/{id}`, `/runs/{id}/cancel`, `/runs/{id}/results`, `/runs/compare/latest`, `/runs/{id}/export` |
| `run_id` format | UUIDv7 |
| `suite_id` format | `{run_id}#v{n}` |
| `eval_id` format | `v{n}-case-{0001}` |
| Summary schema | `title`, `key_points[5]`, `abstract` |
| Judge schema | Four integer scores (0–5), fixed 8-tag taxonomy, hallucination flag, rationale <=60 words, evidence spans <=2 |
| Run status values | `queued / running / completed / completed_with_errors / failed` |

---

## Acceptance Test Scenarios

| # | Scenario | Pass Condition |
|---|---|---|
| 1 | Determinism | Same seed yields identical sampled corpus and suite balancing |
| 2 | Hallucination enforcement | Flagged case always fails regardless of aggregate score |
| 3 | Partial failure | Case-level external errors still produce finalized run with `completed_with_errors` |
| 4 | Token cap | Graceful stop preserves partial metrics and explicit termination reason |
| 5 | Queueing | Second run enters `queued` and starts only after active run finishes/cancels |
| 6 | Curriculum | v2 keeps 40% regression core and 60% new cases while meeting difficulty mix |
| 7 | Dedup | Similarity >=0.90 prevents near-duplicate eval prompt insertion |
| 8 | Dashboard | UI correctly renders v1/v2 metrics, failure tags, worst cases, and latest comparison |

---

## Explicit Defaults and Assumptions

| Setting | Value |
|---|---|
| Model | `gemini-2.0-flash`, temperature 0 |
| Embeddings | `text-embedding-004` |
| Pinecone | Single project-named index, AWS `us-east-1`, namespaces: `eval_prompts`, `failures` |
| DynamoDB | Local container `http://dynamodb-local:8000`, region `us-east-1` |
| Token cap | 300k per run |
| Iterations | 2 (v1 + v2) |
| Suite size | 20 cases |
| Workers | 4 |
| Corpus size | 150 docs |
| Seed default | `42` |
| Pass threshold | Aggregate >= 3.5 AND no hallucination flag |
| Active runs | One at a time, FIFO queue, soft cancel, no resume after process restart |
