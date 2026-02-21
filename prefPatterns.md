# Preferred Patterns Reference

> Derived from the deepthought project. These conventions should be followed throughout AutoEval-Sum unless a specific decision overrides them.

---

## Project Structure

```
project/
├── apps/
│   ├── backend/
│   │   ├── src/<package_name>/   # Namespace packaging (src layout)
│   │   │   ├── agents/
│   │   │   ├── api/
│   │   │   ├── config/
│   │   │   ├── core/
│   │   │   ├── db/
│   │   │   ├── llm/
│   │   │   ├── models/
│   │   │   └── tools/
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   └── integration/
│   │   ├── scripts/              # Infra setup scripts
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   └── frontend/
│       ├── src/
│       │   ├── app/              # Next.js App Router
│       │   ├── components/
│       │   │   └── ui/           # Reusable primitives
│       │   ├── contexts/
│       │   ├── hooks/
│       │   └── lib/              # API client + types
│       ├── Dockerfile
│       └── package.json
├── infra/
├── artifacts/exports/
├── data/                         # gitignored
├── docker-compose.yml
└── Makefile
```

---

## Backend

### Framework & Entry Point
- **FastAPI** with `create_app()` factory pattern in `api/app.py`
- Version defined in `__init__.py` as `__version__ = "0.1.0"`
- Python 3.11+, modern union syntax (`str | None`, `int | float`)

### Configuration
```python
# config/settings.py
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    # Typed fields — startup fails fast on missing required vars

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### Dependency Injection
Generator-based deps with `Depends`, one function per resource:
```python
def get_runs_db_client() -> Generator[DynamoDBClient, None, None]:
    settings = get_settings()
    client = DynamoDBClient(table_name=settings.dynamodb_runs_table, ...)
    yield client

@lru_cache
def get_agent_graph() -> CompiledStateGraph:
    return compile_graph()
```

### Error Handling
Custom exception hierarchy rooted at a base project error:
```python
class AutoEvalError(Exception): ...
    class AgentExecutionError(agent_name, msg): ...
    class DatabaseError: ...
    class NotFoundError(resource, identifier): ...
```
Always chain with `raise X from e`. Wrap in `HTTPException` at the route layer only.

### API Routes
- Base path `/api/v1`
- One router file per resource group (`ingestion.py`, `runs.py`)
- Typed request/response models on every endpoint
- Status codes: 201 Created, 200 OK, 404 Not Found, 409 Conflict, 500 Internal Error
```python
@router.post("/", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def start_run(
    request: RunStartRequest,
    runs_db: DynamoDBClient = Depends(get_runs_db_client),
    graph: CompiledStateGraph = Depends(get_agent_graph),
) -> RunResponse: ...
```

### Pydantic Models
- Request models: `XCreate`, `XRequest`
- Response models: `XResponse`
- DB models: `X` (includes all fields including internal ones)
- Field validation with `Field(..., ge=0, le=5, description="...")`
- All timestamps: `datetime` typed, UTC ISO 8601 stored as strings

### DynamoDB Client
Async wrapper over `aioboto3` — no ORM:
```python
class DynamoDBClient:
    def __init__(self, table_name: str, region: str, endpoint_url: str | None = None): ...
    async def get_item(self, pk: str, sk: str | None = None) -> dict[str, Any] | None: ...
    async def put_item(self, item: dict[str, Any]) -> None: ...
    async def query(self, pk: str, sk_prefix: str | None = None) -> list[dict[str, Any]]: ...
    async def update_item(self, pk: str, sk: str | None, updates: dict) -> None: ...
    async def delete_item(self, pk: str, sk: str | None = None) -> None: ...
```
Convert floats → `Decimal` before writes. Use `begins_with(sk, :prefix)` for hierarchical queries.

### Composite Key Strategy
- `pk`: primary identifier (e.g., `run_id`)
- `sk`: hierarchical prefix (e.g., `RESULT#{suite_id}#{eval_id}`)
- Enables prefix range queries with `begins_with`

### Naming Conventions (Python)
- Files: `snake_case.py`
- Classes: `PascalCase` — models suffixed `Create/Response`, exceptions suffixed `Error`
- Functions/variables: `snake_case`; private: `_underscore_prefix`
- Constants: `UPPER_SNAKE_CASE`
- Imports: stdlib → third-party → local
- Docstrings: Google style
- Line length: 100 chars (ruff)

### Tooling
- Package manager: `uv`
- Linting/formatting: `ruff` (target py311, line-length 100, select E/F/I/N/W/B/Q)
- Type checking: `mypy` (strict mode, `warn_return_any = true`, `pydantic.mypy` plugin)
- Testing: `pytest` with `asyncio_mode = "auto"`, `pytest-asyncio`, `pytest-cov`, `httpx`

---

## LangGraph Agent Patterns

### State Design
```python
class RunState(TypedDict):
    # Input context
    run_id: str
    seed: int
    corpus_size: int
    suite_size: int
    # Agent outputs
    doc_catalog: list[dict[str, Any]]
    eval_suite_v1: list[dict[str, Any]]
    suite_v1_metrics: dict[str, Any]
    eval_suite_v2: list[dict[str, Any]]
    suite_v2_metrics: dict[str, Any]
    # Messaging
    messages: Annotated[list[BaseMessage], add_messages]
    # Telemetry
    node_timings: dict[str, float]
    # Control flow
    current_step: str
    error: str | None
    token_usage: int
```

### Node Pattern
```python
async def some_node(state: RunState) -> dict[str, Any]:
    start_time = time.perf_counter()

    # ... do work

    duration_ms = (time.perf_counter() - start_time) * 1000
    return {
        "field": result,
        "current_step": "some_node_complete",
        "node_timings": {"some_node": duration_ms},
        "messages": [AIMessage(content="...")],
    }
```

### Routing Pattern
```python
def route_after_node(state: RunState) -> Literal["next_node", "error"]:
    if state.get("error"):
        return "error"
    return "next_node"
```

### Graph Compilation
```python
def create_graph() -> StateGraph[RunState]:
    builder = StateGraph(RunState)
    builder.add_node("load_docs", load_docs_node)
    builder.add_conditional_edges("load_docs", route_after_load_docs)
    return builder

def compile_graph() -> CompiledStateGraph:
    return create_graph().compile()
```

### LLM Factory
```python
@lru_cache
def get_llm(model: str | None = None) -> BaseChatModel:
    settings = get_settings()
    return _create_google_llm(model or settings.llm_model, settings.google_api_key)

def get_llm_with_tools(tools: list[Any]) -> BaseChatModel:
    return get_llm().bind_tools(tools)
```

### Prompts
- One prompt file per agent in `agents/prompts/`
- Prompts are constants, decoupled from code, diffable
- Injected as `HumanMessage(content=PROMPT + task_details)`

### Error Recovery
```python
try:
    result = _parse_llm_output(response)
except Exception as e:
    logger.warning(f"LLM parse failed, using fallback: {e}")
    result = _create_fallback(state)
```

---

## Frontend

### Framework
- Next.js App Router (no Pages Router)
- TypeScript strict mode
- Tailwind CSS v4
- TanStack Query for server state
- Axios with interceptors for HTTP

### Directory Conventions
- Directories: `kebab-case`
- Component files: `PascalCase.tsx`
- Hook files: `use-name.ts`
- Type files: `types.ts`

### API Client
```typescript
// lib/api.ts
const api = axios.create({ baseURL: process.env.NEXT_PUBLIC_API_URL });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
```

### Data Fetching Hooks
```typescript
export function useRuns() {
  return useQuery<Run[]>({
    queryKey: ["runs"],
    queryFn: async () => {
      const { data } = await api.get<Run[]>("/runs");
      return data;
    },
  });
}

export function useStartRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (params: RunStartRequest) => {
      const { data } = await api.post<Run>("/runs/start", params);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["runs"] }),
  });
}
```

### Provider Setup
```typescript
// app/providers.tsx — composition pattern
export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
  }));
  return (
    <ThemeProvider attribute="class" defaultTheme="dark">
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    </ThemeProvider>
  );
}
```

### TypeScript Conventions
- Interfaces without `I` prefix: `Run`, `EvalCase`, `JudgeResult`
- Suffixes for clarity: `Request`, `Response`
- Generic hooks: `useQuery<Run[]>`, `useMutation<Run, AxiosError, RunStartRequest>`
- Path aliases: `@/*` → `./src/*`
- `"use client"` directive at top of client components, before imports

### Naming Conventions (TypeScript)
- Variables/functions: `camelCase`
- Event handlers: `on` prefix: `onClick`, `onChange`
- Components: `PascalCase`
- Hooks: `use` prefix: `useRuns`, `useRunStatus`

---

## Docker & Infrastructure

### Compose Service Order
```yaml
dynamodb-local → setup-dynamo (service_completed_successfully)
               → setup-pinecone (independent)
               → backend (depends: setup-dynamo)
               → frontend (depends: backend)
```

### Health Check Pattern
```yaml
healthcheck:
  test: ["CMD-SHELL", "curl -s http://localhost:8000/health || exit 1"]
  interval: 10s
  timeout: 5s
  retries: 3
```

### Dockerfile Patterns
- **Backend:** Single-stage `python:3.11-slim`, install via `pip install -e .`, uvicorn with `--factory`
- **Frontend:** Multi-stage — `node:20-alpine` builder → `node:20-alpine` runner with standalone output

### Volumes & Networks
- Named volume for DynamoDB persistence
- Single named bridge network shared across services
- `.env` files mounted via `env_file`

---

## Makefile Commands (Standard Targets)

```makefile
make install       # Install all deps
make dev           # Full stack local dev
make build         # Docker build
make up            # Compose up
make down          # Compose down
make lint          # ruff + mypy
make test          # pytest
make setup-dynamo  # Create DynamoDB tables
make setup-pinecone # Init Pinecone index
```

---

## General Principles

1. **Async-first** — `async/await` throughout Python and TypeScript
2. **Type safety at boundaries** — Pydantic for Python, strict TS interfaces for frontend; trust internals
3. **Dependency injection** — FastAPI `Depends` for loose coupling and testability
4. **Telemetry built-in** — Per-node timing captured from day one (`time.perf_counter()`)
5. **Idempotent setup scripts** — Infra scripts always check before creating; safe to re-run
6. **Separation of concerns** — Agents, API layer, DB layer, and LLM factory are fully independent modules
7. **Fallback on agent errors** — LLM parse failures use structured fallback, not hard crash
8. **Single source of truth** — Settings come from one `get_settings()` call cached with `lru_cache`
9. **Small commits, full messages** — Commit often with holistic bullet-point descriptions
