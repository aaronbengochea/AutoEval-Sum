"""
Run lifecycle API routes.

POST /api/v1/runs/start         — enqueue a new run and start it in the background
GET  /api/v1/runs/{run_id}      — get run status and summary metrics
POST /api/v1/runs/{run_id}/cancel — request soft cancellation
GET  /api/v1/runs/{run_id}/results — full results: run record + suite metrics
GET  /api/v1/runs/compare/latest   — compare the two most recent completed runs
GET  /api/v1/runs/{run_id}/export  — write full run data to artifacts/exports/
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

import uuid6
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from autoeval_sum.api.dependencies import get_runs_db, get_suites_db
from autoeval_sum.config.settings import get_settings
from autoeval_sum.db.client import DynamoDBClient
from autoeval_sum.db.runs import get_run, save_run, update_run_status
from autoeval_sum.db.suites import list_suites_for_run
from autoeval_sum.models.runs import RunConfig, RunRecord, RunStatus
from autoeval_sum.runtime.graph import build_graph
from autoeval_sum.runtime.queue import get_run_queue
from autoeval_sum.vector.client import get_pinecone_client

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])
log = logging.getLogger(__name__)

EXPORTS_DIR = Path(os.getenv("EXPORTS_DIR", "artifacts/exports"))


# ── Request / Response models ─────────────────────────────────────────────────

class RunStartRequest(BaseModel):
    seed: int = Field(default=42, description="RNG seed for deterministic corpus sampling")
    corpus_size: int = Field(default=150, ge=1, description="Number of documents to load")
    suite_size: int = Field(default=20, ge=1, description="Eval cases per iteration")


class RunStartResponse(BaseModel):
    run_id: str
    status: str
    message: str


class RunStatusResponse(BaseModel):
    run_id: str
    status: str
    config: dict[str, Any]
    created_at: str
    started_at: str | None
    completed_at: str | None
    error_message: str | None
    metrics_v1: dict[str, Any] | None
    metrics_v2: dict[str, Any] | None


class CancelResponse(BaseModel):
    run_id: str
    cancel_requested: bool
    message: str


class RunResultsResponse(BaseModel):
    run_id: str
    status: str
    metrics_v1: dict[str, Any] | None
    metrics_v2: dict[str, Any] | None
    suites: list[dict[str, Any]]


# ── Background run executor ───────────────────────────────────────────────────

async def _execute_run(run_id: str, config: RunConfig) -> None:
    """
    Long-running background coroutine that drives the full v1→v2 eval loop.

    Creates fresh DB/vector clients from settings (FastAPI DI is not available
    in background tasks).  Acquires the run queue, invokes the compiled graph,
    and ensures the run status is always written to DynamoDB even on failure.
    """
    settings = get_settings()

    def _db(table_name: str) -> DynamoDBClient:
        return DynamoDBClient(
            table_name=table_name,
            region=settings.aws_region,
            endpoint_url=settings.dynamodb_endpoint_url,
        )

    runs_db = _db(settings.dynamodb_runs_table)
    docs_db = _db(settings.dynamodb_documents_table)
    suites_db = _db(settings.dynamodb_suites_table)
    results_db = _db(settings.dynamodb_results_table)

    try:
        vector_client = get_pinecone_client()
    except Exception as exc:
        log.warning("Pinecone unavailable; running without vector memory: %s", exc)
        vector_client = None

    graph = build_graph(
        docs_db=docs_db,
        runs_db=runs_db,
        suites_db=suites_db,
        results_db=results_db,
        vector_client=vector_client,
    )

    initial_state = {
        "run_id": run_id,
        "seed": config.seed,
        "corpus_size": config.corpus_size,
        "suite_size": config.suite_size,
    }

    queue = get_run_queue()
    try:
        async with queue.acquire(run_id, runs_db):
            log.info("Run %s: graph execution started.", run_id)
            await graph.ainvoke(initial_state)
            log.info("Run %s: graph execution complete.", run_id)
    except Exception as exc:
        log.error("Run %s: unexpected error in graph: %s", run_id, exc)
        try:
            await update_run_status(
                run_id, RunStatus.failed, runs_db, error_message=str(exc)
            )
        except Exception:
            log.exception("Failed to mark run %s as failed after graph error.", run_id)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "/start",
    response_model=RunStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a new evaluation run",
    description=(
        "Creates a run record with status=queued, then starts the full v1→v2 eval "
        "pipeline in the background.  Only one run executes at a time; concurrent "
        "starts are serialised via an in-process FIFO queue."
    ),
)
async def start_run(
    request: RunStartRequest,
    runs_db: DynamoDBClient = Depends(get_runs_db),
) -> RunStartResponse:
    run_id = str(uuid6.uuid7())
    config = RunConfig(
        seed=request.seed,
        corpus_size=request.corpus_size,
        suite_size=request.suite_size,
    )
    run = RunRecord.create(run_id, config)
    await save_run(run, runs_db)

    # Fire-and-forget: asyncio.create_task keeps the coroutine alive past the
    # HTTP response without blocking the caller.
    asyncio.create_task(_execute_run(run_id, config))

    queue = get_run_queue()
    queue_msg = "Running immediately" if not queue.is_busy else "Queued behind active run"

    log.info(
        "Run %s enqueued (seed=%d, corpus=%d, suite=%d).",
        run_id, request.seed, request.corpus_size, request.suite_size,
    )
    return RunStartResponse(
        run_id=run_id,
        status=RunStatus.queued.value,
        message=queue_msg,
    )


@router.get(
    "/{run_id}",
    response_model=RunStatusResponse,
    summary="Get run status",
    description="Returns the current status and top-level metrics for a run.",
)
async def get_run_status(
    run_id: str,
    runs_db: DynamoDBClient = Depends(get_runs_db),
) -> RunStatusResponse:
    run = await get_run(run_id, runs_db)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run {run_id} not found")
    return RunStatusResponse(
        run_id=run.run_id,
        status=run.status.value,
        config=run.config.model_dump(),
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        error_message=run.error_message,
        metrics_v1=run.metrics_v1,
        metrics_v2=run.metrics_v2,
    )


@router.post(
    "/{run_id}/cancel",
    response_model=CancelResponse,
    summary="Cancel an active run",
    description=(
        "Signals the active run to stop at the next eval-case boundary.  "
        "If the run_id is not currently active, cancel_requested will be False."
    ),
)
async def cancel_run(
    run_id: str,
    runs_db: DynamoDBClient = Depends(get_runs_db),
) -> CancelResponse:
    run = await get_run(run_id, runs_db)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run {run_id} not found")

    queue = get_run_queue()
    if queue.active_run_id != run_id:
        return CancelResponse(
            run_id=run_id,
            cancel_requested=False,
            message="Run is not currently active; cancel has no effect.",
        )

    cancelled = queue.request_cancel()
    return CancelResponse(
        run_id=run_id,
        cancel_requested=cancelled,
        message=(
            "Cancel signal sent; run will stop at the next case boundary."
            if cancelled else "No active run."
        ),
    )


@router.get(
    "/{run_id}/results",
    response_model=RunResultsResponse,
    summary="Get run results",
    description="Returns the run record plus both suite metric snapshots from DynamoDB.",
)
async def get_run_results(
    run_id: str,
    runs_db: DynamoDBClient = Depends(get_runs_db),
    suites_db: DynamoDBClient = Depends(get_suites_db),
) -> RunResultsResponse:
    run = await get_run(run_id, runs_db)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run {run_id} not found")

    suites = await list_suites_for_run(run_id, suites_db)

    return RunResultsResponse(
        run_id=run.run_id,
        status=run.status.value,
        metrics_v1=run.metrics_v1,
        metrics_v2=run.metrics_v2,
        suites=suites,
    )
