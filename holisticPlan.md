# AutoEval-Sum v1 — Holistic Implementation Plan

> This document serves as the grounding rubric for the AutoEval-Sum project. It captures the full architectural vision, schemas, agent contracts, and acceptance criteria. Phase-by-phase execution plans are maintained separately.

---

## Summary

1. Build a Dockerized monorepo with `apps/frontend` (Next.js + TypeScript) and `apps/backend` (FastAPI + LangGraph/LangChain), plus local DynamoDB and cloud Pinecone.
2. Execute a fully autonomous two-iteration loop (`v1` then `v2`) against a fixed summarizer-under-test, with strict judge scoring and curriculum-based suite evolution.
3. Optimize for technical-demo credibility: reproducible runs, auditable storage, deterministic prompts/settings, and explicit v1→v2 improvement KPIs.

---

## Scope and Success Criteria

1. **Goal:** Autonomously improve evaluation suite quality (not summarizer quality) for summarization testing.
2. **Primary KPI:** Failure detection rate increase from `suite v1` to `suite v2`.
3. **Secondary KPI:** Unique failure-tag coverage increase from `suite v1` to `suite v2`.
4. **Constraints:**
   - Single Gemini model for all agents
   - 2 iterations
   - 20 eval cases per suite
   - Token cap: 300k/run
   - Target runtime: <= 15 minutes
   - No auth
   - Manual run trigger

---

## Monorepo and Tooling

1. **Layout:** `apps/frontend`, `apps/backend`, `infra`, `artifacts/exports`, `data` (gitignored).
2. **Backend tooling:** `uv`, `pyproject.toml`, `ruff`, `mypy`, `pytest`.
3. **Frontend tooling:** `pnpm`, Next.js App Router, Tailwind CSS, TanStack Query, Recharts, custom lightweight components.
4. **Command interface:** Root `Makefile` wrapping build/run/test/lint/init tasks.
5. **CI:** Basic workflow for lint + unit/contract tests, with external dependencies mocked.

---

## Public APIs, Interfaces, and Types

| Endpoint | Body / Query | Action | Response |
|---|---|---|---|
| `POST /ingestion/prepare` | `{ seed, corpus_size }` | Fetch/filter/cache MSMARCO docs, write metadata | `{ ingestion_id, accepted_count, status }` |
| `GET /ingestion/status` | `?ingestion_id=` (optional) | Return ingestion state | Counts and cache hit/miss |
| `POST /runs/start` | `{ seed, corpus_size, suite_size }` | Enqueue run | `{ run_id, status: "queued" }` |
| `POST /runs/{run_id}/cancel` | — | Soft-cancel at case boundary | `{ run_id, status }` |
| `GET /runs/{run_id}` | — | Run metadata and status | Run object |
| `GET /runs/{run_id}/results` | — | Full structured run output | Results object |
| `GET /runs/{run_id}/export` | — | Write and return JSON export path | Export path in `artifacts/exports/` |
| `GET /runs/compare/latest` | — | Current run vs most recent completed | Comparison object |

**Run status values:** `queued | running | completed | completed_with_errors | failed`

---

## Core JSON Schemas

### SummaryStructured
```json
{
  "title": "string",
  "key_points": ["string (<=24 words) x5"],
  "abstract": "string (<=120 words)"
}
```

### EvalCase
```json
{
  "eval_id": "string",
  "doc_id": "string",
  "prompt_template": "string",
  "constraints": "object",
  "rubric_note": "string",
  "difficulty_tag": "easy|medium|hard",
  "category_tag": "string"
}
```

### RubricGlobal
Fixed dimensions: `coverage`, `faithfulness`, `conciseness`, `structure`
Anchors at `0`, `3`, `5` for each dimension.

### JudgeCaseResult
```json
{
  "eval_id": "string",
  "scores": {
    "coverage": "int 0-5",
    "faithfulness": "int 0-5",
    "conciseness": "int 0-5",
    "structure": "int 0-5"
  },
  "aggregate_score": "float",
  "hallucination_flag": "bool",
  "failure_tags": ["string"],
  "rationale": "string (<=60 words)",
  "evidence_spans": ["string (0..2 items)"],
  "pass": "bool"
}
```

### SuiteMetrics
```json
{
  "suite_id": "string",
  "avg_scores_by_dimension": "object",
  "aggregate_avg": "float",
  "pass_rate": "float",
  "failure_detection_rate": "float",
  "top_failure_modes": ["string (top 5)"],
  "worst_examples": ["EvalCase (5 items)"]
}
```

### CurriculumOutput
```json
{
  "next_suite": "EvalCase[]",
  "improvement_plan": {
    "retained_count": "int",
    "replaced_count": "int",
    "targeted_failure_modes": ["string"],
    "dedup_rejections": "int",
    "representative_changes": "string"
  }
}
```

---

## Agent Contracts

| Agent | Input | Output | Notes |
|---|---|---|---|
| **Summarizer** | `{ doc_text_truncated, constraints }` | `SummaryStructured` | Temperature 0 |
| **Eval Author** | `{ agent_spec, doc_catalog, suite_size, difficulty_mix, category_targets }` | `eval_suite_v1` | Single canonical prompt template |
| **Judge** | `{ doc_text_truncated, summary_structured, rubric_global, rubric_note }` | `JudgeCaseResult` (strict JSON) | Hallucination = auto-fail |
| **Curriculum** | `{ history, suite_v1_metrics, top_failure_modes, worst_examples, doc_catalog, pinecone_context }` | `eval_suite_v2` | 60% new / 40% regression core; concise diff plan |

---

## Failure Taxonomy (Fixed 8 Tags)

| Tag | Description |
|---|---|
| `missed_key_point` | Summary omits a key point from the source |
| `hallucinated_fact` | Summary asserts a fact not present in source |
| `unsupported_claim` | Claim made without source evidence |
| `verbosity_excess` | Summary is unnecessarily verbose |
| `over_compression` | Summary loses too much detail |
| `poor_structure` | Summary is poorly organized |
| `topic_drift` | Summary shifts to off-topic content |
| `entity_error` | Named entities misrepresented or confused |

---

## Dataset and Ingestion Spec

1. **Source:** Hugging Face `microsoft/ms_marco` docs split.
2. **Sampling:** Seeded random sample, deterministic by `seed`.
3. **Filters:** English only AND >= 500 words.
4. **Corpus default:** 150 docs (accepted range: 100–200).
5. **Storage:** Full text in local gitignored `data/` volume; metadata in DynamoDB `Documents`.
6. **Category assignment:** LLM auto-classification (fixed enum list in prompt).
7. **Difficulty tagging heuristic:**
   - Easy: 500–900 words AND entity_density < 0.08
   - Medium: 901–1500 words OR 0.08–0.14
   - Hard: > 1500 words OR > 0.14
8. **Entity density:** spaCy `en_core_web_sm` installed during backend image build.
9. **Truncation:** Max 2048 tokens using Gemini `count_tokens`; truncation logged per case.

---

## LangGraph Orchestration

1. **Queue model:** Single active run with FIFO queue for additional starts.
2. **Node flow:**
   ```
   load_docs → init_run → eval_author_v1 → execute_v1 → judge_v1
             → curriculum_v2 → execute_v2 → judge_v2 → finalize
   ```
3. **Execution policy:** Auto-execute `v2` once generated.
4. **Per-suite execution:** Bounded parallelism with 4 workers.
5. **Retries:** Exponential backoff with jitter, max 3 retries per external call.
6. **Token cap policy:** Graceful stop with partial finalization and status `completed_with_errors`.
7. **Restart policy:** If backend restarts mid-run, mark run `failed` and require manual restart.
8. **Cancel policy:** Soft cancel at case boundary with consistent persisted state.

---

## Persistence Design

### DynamoDB Local
- **Endpoint:** `http://dynamodb-local:8000`
- **Region:** `us-east-1`

### Tables (4 total)

| Table | Purpose |
|---|---|
| `AutoEvalRuns` | Run config, status, timestamps, token usage, summary metrics, structured run events |
| `Documents` | `doc_id`, metadata, `content_path`, word/token stats, category, difficulty signals |
| `EvalSuites` | Suite metadata, version, global rubric, case list snapshot, generation provenance |
| `EvalResults` | Per-case summary output, scorecard, failure tags, operational errors |

### ID Formats
- `run_id`: UUIDv7
- `suite_id`: `{run_id}#v{n}`
- `eval_id`: `v{n}-case-{0001}`
- `result_id`: `{suite_id}#{eval_id}`

**Timestamps:** UTC ISO 8601. **Retention:** Keep all runs by default.

---

## Pinecone Design

1. **Index:** One index (project-name based), AWS `us-east-1`, cosine metric, dimension from embedding output.
2. **Embeddings:** Google `text-embedding-004`.
3. **Namespaces:** `eval_prompts`, `failures`.
4. **Dedup rule:** Reject candidate eval if max cosine similarity >= 0.90 against `eval_prompts`.
5. **Stored metadata:** `run_id`, `suite_version`, `eval_id`, `doc_id`, `difficulty_tag`, `category_tag`, `failure_tags`, `aggregate_score`.

---

## Curriculum Logic for v2

1. **Keep 40% regression core (8/20):** Select worst failures first, then diversity-sample across category/difficulty.
2. **Generate 60% new cases (12/20):** Target top failure modes proportionally, with difficulty/category balancing.
3. **Enforce 30/40/30 easy/medium/hard mix** on final suite.
4. **Use Pinecone similarity checks** to avoid prompt duplication.
5. **Produce structured `improvement_plan`** with counts and rationale for each major change.

---

## Frontend Plan

### Dashboard Sections
- Run controls
- Status/timeline
- Metrics cards
- Failure-tag distribution
- Worst 5 cases table
- v1/v2 diff panel
- Latest-vs-previous run comparison

### Interaction Model
- Manual run trigger
- Polling for run status/results
- Cancel action
- Export JSON action

### Data Path
Next.js server-side proxy routes → backend REST API

---

## Infrastructure and Startup

### Docker Compose Services
- `frontend`
- `backend`
- `dynamodb-local`

Pinecone remains managed cloud; key provided via `.env`.

### Init Scripts (run idempotently via compose startup)
1. Create DynamoDB tables if missing.
2. Create Pinecone index/namespaces if missing.
3. No data seeding required.

### Config Management
Typed `.env` validation at backend/frontend startup.

---

## Test Plan and Acceptance Scenarios

### Test Layers
1. **Unit tests:** Schema validation, pass/fail calculation, KPI aggregation, difficulty tagging, dedup threshold behavior.
2. **Contract tests:** API request/response shapes and status transitions.
3. **Integration tests (mocked externals):** Full graph run with fixture corpus through `v1` and `v2`.
4. **Optional live smoke test:** Real Gemini/Pinecone/local DynamoDB with reduced corpus/suite settings.

### Acceptance Scenarios

| Scenario | Description |
|---|---|
| **A** | Default run (`seed=42, corpus=150, suite=20`) completes with persisted `v1` and `v2`, metrics, and export artifact |
| **B** | Token cap reached → `completed_with_errors` with partial metrics and explicit termination reason |
| **C** | Partial external-call failures recorded per case; run still finalizes |
| **D** | Rerun with same seed reproduces corpus sample and deterministic suite composition constraints |

---

## Explicit Defaults and Assumptions

| Setting | Value |
|---|---|
| Default seed | `42` |
| Default corpus_size | `150` |
| Default suite_size | `20` |
| Prompt language | English only |
| Model | `gemini-2.0-flash`, temperature 0 |
| Pass threshold | aggregate >= 3.5 AND no hallucination flag |
| Worst examples | Top 5 lowest aggregate score |
| Top failure modes | Top 5 by frequency |
| Auth | None (local demo trust model) |
| MSMARCO split error | Fail fast with actionable error and config override path |
