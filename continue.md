# AutoEval-Sum — Session Continuation Guide

> Read this at the start of every new session to restore full context before touching any code.
> Reference `phasedPlan.md` for the full execution roadmap and `holisticPlan.md` for architectural decisions.

---

## Current Status

**Phases complete:** 0, 1, 2, 3, 4, 5
**Next up:** Phase 6 — FastAPI Public API Layer

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
### Phase 4 — LangGraph Runtime and Run Control ✅
### Phase 5 — Persistence + Pinecone Memory Integration ✅
- `models/schemas.py` — All agent I/O schemas:
  - `SummaryStructured` (5 key_points ≤24 words, abstract ≤120 words, validators)
  - `EvalCase`, `RubricGlobal` / `RubricAnchors`, `ScoreCard`
  - `JudgeCaseResult` (rationale ≤60 words, FailureTag Literal, hallucination auto-fail model_validator)
  - `SuiteMetrics`, `CurriculumOutput` / `ImprovementPlan`
- `agents/prompts/rubric.py` — `GLOBAL_RUBRIC` instance, `RUBRIC_TEXT`, `FAILURE_TAXONOMY`
- `agents/prompts/summarizer.py` — `SUMMARIZER_SYSTEM_PROMPT` + `SUMMARIZER_USER_TEMPLATE`
- `agents/prompts/eval_author.py` — `EVAL_AUTHOR_SYSTEM_PROMPT`
- `agents/prompts/judge.py` — `JUDGE_SYSTEM_PROMPT` + `JUDGE_USER_TEMPLATE`
- `agents/prompts/curriculum.py` — `CURRICULUM_SYSTEM_PROMPT`
- `agents/summarizer.py` — `run_summarizer()`, `AgentError` exception
- `agents/eval_author.py` — `run_eval_author()`
- `agents/judge.py` — `run_judge()` (canonically recomputes aggregate + pass)
- `agents/curriculum.py` — `run_curriculum()`

---

## Phase 4 — Completed ✅

- `models/runs.py` — RunStatus enum, RunConfig, RunRecord
- `db/runs.py` — save/get/update/list/mark_stale_runs_failed
- `runtime/queue.py` — RunQueue singleton (asyncio.Lock, cancel flag)
- `runtime/state.py` — RunState TypedDict, CaseExecution TypedDict
- `runtime/nodes/` — load_docs, init_run, eval_author (v1), execute (v1/v2), judge (v1/v2), curriculum_v2, finalize, helpers
- `runtime/graph.py` — build_graph() factory; conditional routing to finalize on cancel
- `runtime/policies.py` — TokenBudgetExceededError, with_retry, make_semaphore
- `api/app.py` — lifespan hook marks orphaned running→failed on startup

## Phase 5 — Completed ✅

- `db/suites.py` — save/get/list for EvalSuites (pk=run_id, sk=suite_version)
- `db/results.py` — save/get/list for EvalResults (pk=suite_id, sk=eval_id)
- `vector/client.py` — PineconeClient: embed_text (text-embedding-004), upsert_vectors, embed_and_upsert, query_similar; get_pinecone_client() singleton
- `vector/dedup.py` — is_near_duplicate (cosine >= 0.90), filter_duplicates
- `vector/memory.py` — upsert_eval_prompts, store_failures, retrieve_failure_exemplars
- Judge nodes: persist results to EvalResults; store failures in Pinecone; retrieve exemplars for v1
- Curriculum node: consume failure exemplars from state; dedup filter v2 candidates; upsert accepted v2 prompts
- Eval author node: upsert v1 prompts after generation
- build_graph(): now accepts suites_db, results_db, vector_client (all optional)

## Phase 6 — What Needs to Be Built Next

### Subphase 6.1: Implement ingestion endpoints
- `POST /ingestion/prepare` and `GET /ingestion/status` (already exists from Phase 2 - may need review)

### Subphase 6.2: Implement run lifecycle endpoints
- `POST /runs/start`, `GET /runs/{id}`, `POST /runs/{id}/cancel`, `GET /runs/{id}/results`

### Subphase 6.3: Implement comparison/export endpoints
- `GET /runs/compare/latest`, `GET /runs/{id}/export` → writes to `artifacts/exports/`

### Subphase 6.4: Publish OpenAPI docs and error contracts
- Typed request/response models for all routes; self-documenting OpenAPI spec

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
│   └── routes/
│       ├── health.py        ← /health + /health/ready
│       └── ingestion.py     ← /api/v1/ingestion/prepare + /status
├── db/
│   ├── client.py            ← async DynamoDBClient (aioboto3)
│   └── runs.py              ← save/get/update/list/mark_stale_runs_failed
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
└── runtime/
    ├── queue.py             ← RunQueue singleton (Lock + cancel flag)
    ├── state.py             ← RunState TypedDict, CaseExecution
    ├── policies.py          ← TokenBudgetExceededError, with_retry, make_semaphore
    ├── graph.py             ← build_graph() → CompiledStateGraph
    └── nodes/
        ├── helpers.py       ← doc_from_dynamo_item, compute_suite_metrics
        ├── load_docs.py
        ├── init_run.py
        ├── eval_author.py   ← make_eval_author_node(version)
        ├── execute.py       ← make_execute_node(version)
        ├── judge.py         ← make_judge_node(version)
        ├── curriculum.py
        └── finalize.py
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
- Latest commit: Phase 5.4 (Failure memory + full Pinecone integration)
