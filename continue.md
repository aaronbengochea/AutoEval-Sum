# AutoEval-Sum — Session Continuation Guide

> Read this at the start of every new session to restore full context before touching any code.
> Reference `phasedPlan.md` for the full execution roadmap and `holisticPlan.md` for architectural decisions.

---

## Current Status

**Phases complete:** 0, 1, 2, 3, 4, 5, 6
**Next up:** Phase 7 — Frontend Dashboard (Next.js)

All completed subphases are marked `[X]` in `phasedPlan.md`.

---

## What Has Been Built

### Phase 0 — Project Foundation ✅
- Monorepo: `apps/backend/`, `apps/frontend/`, `infra/`, `artifacts/exports/`, `data/` (gitignored)
- Backend: `uv` + `pyproject.toml` (full dep set), `ruff`, `mypy` strict, `pytest` asyncio_mode=auto
- Frontend: `pnpm` + `package.json` (Next.js 15, TanStack Query, Recharts, Tailwind v4)
- Root `Makefile` with install/dev/build/lint/test/setup targets
- `docker-compose.yml` with `dynamodb-local`, `setup-dynamo`, `setup-pinecone`, `backend`, `frontend`
- Typed `Settings` (Pydantic BaseSettings + `@lru_cache`) in `config/settings.py`
- Frontend env contract in `apps/frontend/src/lib/env.ts`
- `.env.example` with all vars documented

### Phase 1 — Infra Bootstrap ✅
- `scripts/setup_dynamodb.py` — idempotent table creation for 4 tables
- `scripts/setup_pinecone.py` — idempotent index creation, all config from env
- `api/routes/health.py` — `/health` (liveness) + `/health/ready` (DynamoDB + Pinecone probes)
- Compose updated: `setup-dynamo` and `setup-pinecone` one-shot services; backend waits on both

### Phase 2 — Dataset Ingestion ✅
- `models/documents.py` — `RawDocument`, `EnrichedDocument` Pydantic models
- `ingestion/fetcher.py` — HF datasets loader, SHA-256 stable doc IDs, writes to `data/corpus/`
- `ingestion/filters.py` — ASCII-ratio English check + 500-word minimum + `random.Random(seed)` sampling
- `ingestion/enrichment.py` — Gemini `count_tokens` + binary-search truncation to 2048 tokens, spaCy entity density, difficulty tagging (exact plan thresholds), Gemini category classification (14-item enum, temp=0)
- `db/client.py` — async `DynamoDBClient` (aioboto3, float→Decimal, composite pk/sk)
- `ingestion/persist.py` — save/get/list for Documents table
- `api/dependencies.py` — 4 DI generator providers (documents, runs, suites, results)
- `api/routes/ingestion.py` — `POST /api/v1/ingestion/prepare` + `GET /api/v1/ingestion/status`

### Phase 3 — Agent Contracts and Prompt Assets ✅
- `models/schemas.py` — All agent I/O schemas
- Prompt files in `agents/prompts/` (rubric, summarizer, eval_author, judge, curriculum)
- Agent modules in `agents/` (summarizer, eval_author, judge, curriculum)

### Phase 4 — LangGraph Runtime and Run Control ✅
- `models/runs.py` — RunStatus enum, RunConfig, RunRecord
- `db/runs.py` — save/get/update/list/mark_stale_runs_failed
- `runtime/queue.py` — RunQueue singleton (asyncio.Lock, cancel flag)
- `runtime/state.py` — RunState TypedDict, CaseExecution TypedDict
- `runtime/nodes/` — load_docs, init_run, eval_author (v1), execute (v1/v2), judge (v1/v2), curriculum_v2, finalize, helpers
- `runtime/graph.py` — build_graph() factory; conditional routing to finalize on cancel
- `runtime/policies.py` — TokenBudgetExceededError, with_retry, make_semaphore
- `api/app.py` — lifespan hook marks orphaned running→failed on startup

### Phase 5 — Persistence + Pinecone Memory Integration ✅
- `db/suites.py` — save/get/list for EvalSuites (pk=run_id, sk=suite_version)
- `db/results.py` — save/get/list for EvalResults (pk=suite_id, sk=eval_id)
- `vector/client.py` — PineconeClient: embed_text (text-embedding-004), upsert/query; singleton
- `vector/dedup.py` — is_near_duplicate (cosine >= 0.90), filter_duplicates
- `vector/memory.py` — upsert_eval_prompts, store_failures, retrieve_failure_exemplars
- Nodes wired with vector_client and DB persistence

### Phase 6 — FastAPI Public API Layer ✅
- `api/models.py` — shared `ErrorDetail` Pydantic model
- `api/routes/runs.py` — full run lifecycle router:
  - `POST /api/v1/runs/start` (202) — creates RunRecord, fires _execute_run background task
  - `GET /api/v1/runs/{run_id}` — status, config, timestamps, metrics
  - `POST /api/v1/runs/{run_id}/cancel` — delegates to RunQueue.request_cancel()
  - `GET /api/v1/runs/{run_id}/results` — run record + all suite snapshots
  - `GET /api/v1/runs/compare/latest` — newer/older CompareRunSummary side-by-side
  - `GET /api/v1/runs/{run_id}/export` — writes artifacts/exports/{run_id}.json
- All routes have typed response_model + `responses=` error contracts (404/422/500/503)
- OpenAPI spec auto-generated at `/docs` and `/redoc`

---

## Phase 7 — What Needs to Be Built Next

### Subphase 7.1: Scaffold app shell and data layer
- Set up Tailwind UI shell, TanStack Query, backend proxy routes
- Exit: Polling and API calls work without browser CORS issues

### Subphase 7.2: Build run controls and status timeline
- Manual run trigger, cancel action, live status transitions
- Exit: User can start/monitor/stop runs from UI

### Subphase 7.3: Build results panels
- Metrics cards, failure-tag chart (Recharts), worst 5 cases table, v1/v2 diff summary
- Exit: Technical audience can see improvement narrative directly

### Subphase 7.4: Build historical comparison and export actions
- Current vs most recent completed run comparison panel and export button
- Exit: One-click comparison and artifact retrieval works

---

## Key Architectural Decisions (Locked)

| Decision | Value |
|---|---|
| Model | `gemini-2.0-flash`, temperature 0 |
| Embeddings | `text-embedding-004` |
| DynamoDB tables | `AutoEvalRuns` (pk=run_id), `Documents` (pk=doc_id), `EvalSuites` (pk=run_id, sk=suite_version), `EvalResults` (pk=suite_id, sk=eval_id) |
| run_id format | UUIDv7 |
| suite_id format | `{run_id}#v{n}` |
| eval_id format | `v{n}-case-{0001}` |
| Pass threshold | aggregate >= 3.5 AND NOT hallucination_flag |
| Dedup threshold | cosine similarity >= 0.90 rejects candidate |
| Corpus defaults | seed=42, size=150, suite_size=20 |
| Pinecone index | `autoeval-sum`, AWS us-east-1, cosine, dim=768 |
| Pinecone namespaces | `eval_prompts`, `failures` |
| Failure taxonomy | 8 fixed tags (see models/schemas.py `FailureTag`) |

---

## Backend File Tree (current)

```
apps/backend/src/autoeval_sum/
├── __init__.py
├── config/
│   └── settings.py          ← Pydantic BaseSettings, get_settings()
├── api/
│   ├── app.py               ← create_app() + lifespan (marks stale runs failed)
│   ├── dependencies.py      ← DI generators for 4 DynamoDB tables
│   ├── models.py            ← shared ErrorDetail model
│   └── routes/
│       ├── health.py        ← /health + /health/ready
│       ├── ingestion.py     ← /api/v1/ingestion/prepare + /status
│       └── runs.py          ← /api/v1/runs/* (start, status, cancel, results, compare, export)
├── db/
│   ├── client.py            ← async DynamoDBClient (aioboto3)
│   ├── runs.py              ← save/get/update/list/mark_stale_runs_failed
│   ├── suites.py            ← save/get/list for EvalSuites
│   └── results.py           ← save/get/list for EvalResults
├── ingestion/
│   ├── fetcher.py
│   ├── filters.py
│   ├── enrichment.py
│   └── persist.py
├── models/
│   ├── documents.py         ← RawDocument, EnrichedDocument
│   ├── schemas.py           ← all agent I/O schemas
│   └── runs.py              ← RunStatus enum, RunConfig, RunRecord
├── agents/
│   ├── summarizer.py
│   ├── eval_author.py
│   ├── judge.py
│   ├── curriculum.py
│   └── prompts/
│       ├── rubric.py
│       ├── summarizer.py
│       ├── eval_author.py
│       ├── judge.py
│       └── curriculum.py
├── runtime/
│   ├── queue.py             ← RunQueue singleton (Lock + cancel flag)
│   ├── state.py             ← RunState TypedDict, CaseExecution
│   ├── policies.py          ← TokenBudgetExceededError, with_retry, make_semaphore
│   ├── graph.py             ← build_graph() → CompiledStateGraph
│   └── nodes/
│       ├── helpers.py       ← doc_from_dynamo_item, compute_suite_metrics
│       ├── load_docs.py
│       ├── init_run.py
│       ├── eval_author.py   ← make_eval_author_node(version)
│       ├── execute.py       ← make_execute_node(version)
│       ├── judge.py         ← make_judge_node(version)
│       ├── curriculum.py
│       └── finalize.py
└── vector/
    ├── client.py            ← PineconeClient, get_pinecone_client()
    ├── dedup.py             ← is_near_duplicate, filter_duplicates
    └── memory.py            ← upsert_eval_prompts, store_failures, retrieve_failure_exemplars
```

---

## Conventions To Follow

- **Each subphase = its own commit/push** (unless user explicitly links two)
- **Commit messages:** holistic style, 2–7 bullets, no co-author tags
- **phasedPlan.md:** mark `[X]` on the subphase line at commit time
- **Patterns:** follow `prefPatterns.md` (derived from deepthought project)
- **Settings:** always via `get_settings()`, never `os.getenv` inside app code
- **DI:** FastAPI `Depends` generators, one per table
- **Agents:** always `run_in_executor` for Gemini calls, raise `AgentError` on failure
- **Tests:** venv at `apps/backend/.venv/`, activate with `source apps/backend/.venv/bin/activate`

---

## Git State

- Branch: `main`
- All work committed and pushed to `github.com:aaronbengochea/AutoEval-Sum.git`
- Latest commit: Phase 6.4 (OpenAPI docs and error contracts)
