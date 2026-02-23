# AutoEval-Sum

Autonomous evaluation suite improvement system for summarization testing. AutoEval-Sum runs a deterministic two-iteration loop that generates an initial eval suite (v1), scores it with a judge, learns from the failures, and produces a targeted v2 suite designed to catch more of the same failure modes.

**Primary KPI**: Failure detection rate increase from v1 → v2
**Secondary KPI**: Unique failure-tag coverage expansion

---

## How It Works

```
┌──────────────────────────────────────────────────────────────┐
│                       CORPUS (MSMARCO)                       │
│         Fetch → Filter → Sample → Enrich → Persist           │
└─────────────────────────────┬────────────────────────────────┘
                              │
              ┌───────────────▼───────────────┐
              │         EVAL AUTHOR           │
              │   Generate 20 test cases (v1) │
              │   30/40/30 difficulty mix     │
              └───────────────┬───────────────┘
                              │
              ┌───────────────▼───────────────┐
              │           EXECUTE             │
              │   Summarizer → structured     │
              │   summary per case  (v1 ×20)  │
              └───────────────┬───────────────┘
                              │
              ┌───────────────▼───────────────┐
              │            JUDGE              │
              │   Score 4 dims · flag hallu-  │
              │   cinations · assign tags     │
              │   Compute SuiteMetrics v1     │
              └───────────────┬───────────────┘
                              │
              ┌───────────────▼───────────────┐
              │          CURRICULUM           │
              │   Read v1 failures + Pinecone │
              │   40% retain worst cases      │
              │   60% new targeted cases      │
              └───────────────┬───────────────┘
                              │
              ┌───────────────▼───────────────┐
              │    EXECUTE + JUDGE  (v2 ×20)  │
              │   Same pipeline on new suite  │
              │   Compute SuiteMetrics v2     │
              └───────────────┬───────────────┘
                              │
              ┌───────────────▼───────────────┐
              │           FINALIZE            │
              │   Persist metrics · compare   │
              │   v1 vs v2 failure detection  │
              └───────────────────────────────┘
```

1. **Ingestion** — 50 MSMARCO passages are fetched, filtered, enriched with difficulty/category tags, and persisted to DynamoDB. Text files are written to `data/corpus/`.
2. **v1 Eval Suite** — The Eval Author agent generates 20 test cases with a balanced difficulty mix (30/40/30 easy/medium/hard) using the document catalog.
3. **Execute v1** — The Summarizer agent runs on each case's source document, producing a structured `SummaryStructured` JSON (title, 3–5 key points, abstract).
4. **Judge v1** — The Judge agent scores each summary across four dimensions (coverage, faithfulness, conciseness, structure), flags hallucinations, and assigns failure tags from an 8-tag taxonomy.
5. **Curriculum** — The Curriculum agent reads the v1 metrics and worst-performing cases, queries Pinecone for past failure exemplars, and generates a new v2 suite: 40% retained worst cases, 60% new cases targeting detected failure modes.
6. **Execute v2 + Judge v2** — Same pipeline runs on the improved suite.
7. **Finalize** — Metrics snapshots for both suites are persisted; the UI shows the delta.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 15 (App Router), TanStack Query v5, Recharts, Tailwind CSS 4, TypeScript |
| **Backend** | FastAPI, LangGraph, Python 3.11, Uvicorn |
| **LLM** | Google Gemini 2.0-flash |
| **Embeddings** | Google gemini-embedding-001 (768 dims) |
| **Vector DB** | Pinecone serverless |
| **Database** | DynamoDB Local (dev) / AWS DynamoDB (prod), aioboto3 async client |
| **NLP** | spaCy en_core_web_sm (entity density) |
| **Package Mgr** | uv (backend), pnpm (frontend) |
| **Linting** | ruff + mypy strict (backend), ESLint + tsc (frontend) |

---

## Project Structure

```
autoEvalSum/
├── apps/
│   ├── frontend/                   # Next.js 15 dashboard
│   │   └── src/
│   │       ├── app/                # App Router, API proxy route
│   │       ├── components/         # 7 dashboard panel components
│   │       ├── hooks/              # TanStack Query data hooks
│   │       └── lib/                # Axios client, types, env
│   │
│   └── backend/
│       └── src/autoeval_sum/
│           ├── agents/             # 4 LLM agents + decoupled prompt files
│           ├── api/                # FastAPI routes, DI, app factory
│           ├── config/             # Pydantic BaseSettings
│           ├── db/                 # aioboto3 DynamoDB client + CRUD repos
│           ├── ingestion/          # MSMARCO fetch, filter, enrich, persist
│           ├── models/             # Pydantic schemas (all agent I/O)
│           ├── runtime/            # LangGraph graph, state, queue, nodes
│           └── vector/             # Pinecone client, dedup, failure memory
│
├── data/                           # Gitignored; mounted as Docker volume
│   ├── corpus/                     # Enriched document text files
│   └── hf_cache/                   # HuggingFace datasets cache
│
├── docs/
│   ├── holisticPlan.md             # Full architecture + acceptance criteria
│   ├── phasedPlan.md               # 9-phase execution roadmap
│   ├── continue.md                 # Session handoff + conventions
│   └── prefPatterns.md             # Reference design patterns
│
├── docker-compose.yml
├── Makefile
└── .env.example
```

---

## Quick Start

### Prerequisites

- Docker and Docker Compose
- A [Google AI Studio API key](https://aistudio.google.com/) (Gemini + embeddings)
- A [Pinecone API key](https://www.pinecone.io/)

### 1. Clone and configure

```bash
git clone git@github.com:aaronbengochea/AutoEval-Sum.git
cd AutoEval-Sum
cp .env.example .env
```

Edit `.env` and fill in the two required keys:

```env
GOOGLE_API_KEY=your-google-api-key-here
PINECONE_API_KEY=your-pinecone-api-key-here
```

### 2. Build and start

```bash
make build   # Build all Docker images
make up      # Start all services
```

This runs the full startup sequence automatically:

| Order | Service | What it does |
|---|---|---|
| 1 | `dynamodb-local` | Starts local DynamoDB on port 8000 |
| 2 | `setup-dynamo` | Creates the 4 DynamoDB tables (idempotent) |
| 3 | `setup-pinecone` | Creates the Pinecone index and namespaces (idempotent) |
| 4 | `setup-corpus` | Fetches 50 MSMARCO passages and populates the Documents table |
| 5 | `backend` | Starts the FastAPI server on port 8080 |
| 6 | `dynamodb-admin` | Starts the DynamoDB Admin UI on port 8001 |
| 7 | `frontend` | Starts the Next.js dashboard on port 3000 |

The first boot takes a few minutes while `setup-corpus` downloads and enriches the MSMARCO corpus. Subsequent boots are instant (idempotency checks skip everything).

### 3. Open the dashboard

| Service | URL |
|---|---|
| Dashboard | http://localhost:3000 |
| API docs (Swagger) | http://localhost:8080/docs |
| DynamoDB Admin | http://localhost:8001 |

### 4. Run an eval

Click **Start Run** in the dashboard, or call the API directly:

```bash
curl -X POST http://localhost:8080/api/v1/runs/start \
  -H "Content-Type: application/json" \
  -d '{"seed": 42, "corpus_size": 50, "suite_size": 20}'
```

Poll for status:

```bash
curl http://localhost:8080/api/v1/runs/{run_id}
```

A typical run with 4 workers completes in approximately 2 minutes.

---

## Development

### Install dependencies locally

```bash
make install           # Backend (uv) + frontend (pnpm)
make install-backend
make install-frontend
```

### Run services individually

```bash
make dev-backend       # FastAPI + DynamoDB only (no frontend)
make dev-frontend      # Next.js dev server only
```

### Linting

```bash
make lint              # ruff + mypy + eslint + tsc
make lint-backend
make lint-frontend
```

### Tests

```bash
make test              # All backend tests with coverage
make test-unit
make test-integration
```

---

## API Reference

### Ingestion

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/ingestion/prepare` | Fetch, filter, enrich, and persist corpus |
| `GET` | `/api/v1/ingestion/status` | Corpus stats (doc count, difficulty/category breakdown) |

### Runs

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/runs/start` | Create and enqueue a new eval run |
| `GET` | `/api/v1/runs/compare/latest` | Compare the two most recent completed runs |
| `GET` | `/api/v1/runs/{run_id}` | Run status, config, and metrics snapshot |
| `POST` | `/api/v1/runs/{run_id}/cancel` | Request soft cancellation (stops at next case boundary) |
| `GET` | `/api/v1/runs/{run_id}/results` | Full results: suite data, eval cases, judge scores |
| `GET` | `/api/v1/runs/{run_id}/export` | Export full run data as JSON |

### Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe |
| `GET` | `/health/ready` | Readiness probe (DynamoDB + Pinecone connectivity) |

---

## Environment Variables

Copy `.env.example` to `.env`. Only the two API keys are required; everything else has defaults.

```env
# ── Required ──────────────────────────────────────────────────────────────────
GOOGLE_API_KEY=                          # Google AI Studio key
PINECONE_API_KEY=                        # Pinecone API key

# ── Models ────────────────────────────────────────────────────────────────────
LLM_MODEL=gemini-2.0-flash
EMBEDDING_MODEL=gemini-embedding-001

# ── Pinecone ──────────────────────────────────────────────────────────────────
PINECONE_INDEX_NAME=autoeval-sum
PINECONE_ENVIRONMENT=us-east-1
PINECONE_CLOUD=aws
PINECONE_METRIC=cosine
PINECONE_EMBEDDING_DIMENSION=768

# ── DynamoDB ──────────────────────────────────────────────────────────────────
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=local
AWS_SECRET_ACCESS_KEY=local
DYNAMODB_ENDPOINT_URL=http://dynamodb-local:8000
DYNAMODB_RUNS_TABLE=AutoEvalRuns
DYNAMODB_DOCUMENTS_TABLE=Documents
DYNAMODB_SUITES_TABLE=EvalSuites
DYNAMODB_RESULTS_TABLE=EvalResults

# ── Run Defaults ──────────────────────────────────────────────────────────────
DEFAULT_SEED=42
DEFAULT_CORPUS_SIZE=50
DEFAULT_SUITE_SIZE=20
MAX_TOKEN_BUDGET=300000
RUN_WORKERS=4

# ── MSMARCO Dataset ───────────────────────────────────────────────────────────
MSMARCO_DATASET=microsoft/ms_marco
MSMARCO_CONFIG=v1.1
MSMARCO_SPLIT=train
MSMARCO_SCAN_LIMIT=5000

# ── App ───────────────────────────────────────────────────────────────────────
DEBUG=false
LOG_LEVEL=INFO
DATA_DIR=data

# ── Frontend ──────────────────────────────────────────────────────────────────
NEXT_PUBLIC_API_URL=http://localhost:8080
```

---

## Agents

### Summarizer
Produces a deterministic structured summary from a source document.

- **Input**: Document text (≤2048 tokens), optional per-case constraints
- **Output**: `SummaryStructured` — title, 3–5 key points (≤24 words each), abstract (≤120 words)
- **Retries**: Up to 3 on JSON parse or Pydantic validation failure

### Eval Author
Generates the initial v1 evaluation test suite.

- **Input**: Agent spec, document catalog (doc_id, difficulty, category, word count), suite size
- **Output**: 20 `EvalCase` objects with prompt templates, constraints, rubric notes
- **Constraints**: 30/40/30 easy/medium/hard mix, Pinecone dedup (cosine ≥0.90 rejects)

### Judge
Scores a summary against the source document.

- **Input**: Eval case (rubric note), source document, `SummaryStructured`
- **Output**: `JudgeCaseResult` — per-dimension scores (0–5), aggregate score, hallucination flag, failure tags
- **Pass threshold**: aggregate ≥ 3.5 AND `hallucination_flag = false`
- **Failure taxonomy**: `missed_key_point`, `hallucinated_fact`, `unsupported_claim`, `verbosity_excess`, `over_compression`, `poor_structure`, `topic_drift`, `entity_error`

### Curriculum
Learns from v1 failures and generates the v2 suite.

- **Input**: v1 metrics (pass rate, top failure modes, worst examples), Pinecone failure exemplars
- **Output**: 20 `EvalCase` objects — 40% retained worst cases, 60% new cases targeting failures
- **Constraints**: Same 30/40/30 difficulty mix, Pinecone dedup on all new cases

---

## Database Schema

### DynamoDB Tables

| Table | PK | SK | Key Attributes |
|---|---|---|---|
| `AutoEvalRuns` | `run_id` (UUIDv7) | — | `status`, `config`, `metrics_v1`, `metrics_v2`, timestamps |
| `Documents` | `doc_id` (SHA-256) | — | `content_path`, `word_count`, `token_count`, `entity_density`, `difficulty_tag`, `category_tag` |
| `EvalSuites` | `run_id` | `suite_version` (`v1`/`v2`) | `cases` (JSON list), `generated_at` |
| `EvalResults` | `suite_id` (`{run_id}#v1`) | `eval_id` (`v1-case-0001`) | `scores`, `aggregate_score`, `pass_result`, `failure_tags` |

### Pinecone Namespaces

| Namespace | Content | Purpose |
|---|---|---|
| `eval_prompts` | One vector per EvalCase prompt | Dedup checks during case generation |
| `failures` | One vector per failing judge result | Failure memory for the Curriculum agent |

---

## Run Lifecycle

```
queued → running → completed
                 ↘ completed_with_errors   (token cap hit or partial failures)
                 ↘ failed                  (unrecoverable error)
```

- **Queueing**: Only one run executes at a time; additional requests queue FIFO.
- **Cancellation**: Stops at the next case boundary and routes to `finalize` for consistent state.
- **Token budget**: Configurable via `MAX_TOKEN_BUDGET` (default 300k per run).
- **Retries**: Each agent retries up to 3 times with exponential backoff on validation failure.

---

## Corpus Details

Documents are sourced from [MS MARCO](https://huggingface.co/datasets/microsoft/ms_marco) (v1.1, train split).

1. **Fetch** — Stream up to `MSMARCO_SCAN_LIMIT` passages from HuggingFace (cached to `data/hf_cache/`)
2. **Filter** — Keep passages ≥90% printable ASCII with ≥50 words
3. **Sample** — Deterministically select `DEFAULT_CORPUS_SIZE` documents using seeded RNG
4. **Enrich** — Token count (Gemini), entity density (spaCy), difficulty tag, category classification (Gemini, 14-item taxonomy)
5. **Persist** — Metadata to DynamoDB `Documents` table; text to `data/corpus/{doc_id}.txt`

| Difficulty | Criteria |
|---|---|
| `easy` | ≤75 words AND entity density <0.06 |
| `hard` | >150 words OR entity density >0.12 |
| `medium` | Everything else |

---

## Makefile Reference

```bash
make install           # Install all dependencies
make build             # Build all Docker images (--no-cache)
make up                # Start all services (detached)
make down              # Stop all services
make dev               # Full stack, attached logs
make dev-backend       # Backend + DynamoDB only
make dev-frontend      # Next.js dev server only
make lint              # All linters
make lint-backend      # ruff + mypy
make lint-frontend     # eslint + tsc
make test              # Backend tests with coverage
make test-unit
make test-integration
make clean             # Remove build artifacts
```
