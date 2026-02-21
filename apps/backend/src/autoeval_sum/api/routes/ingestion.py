"""
Ingestion API routes.

POST /api/v1/ingestion/prepare  — fetch, filter, enrich, and persist corpus
GET  /api/v1/ingestion/status   — return corpus stats from the Documents table
"""

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from autoeval_sum.api.dependencies import get_documents_db
from autoeval_sum.api.models import ErrorDetail
from autoeval_sum.config.settings import get_settings
from autoeval_sum.db.client import DynamoDBClient
from autoeval_sum.ingestion.enrichment import enrich_documents
from autoeval_sum.ingestion.fetcher import fetch_raw_documents
from autoeval_sum.ingestion.filters import filter_documents, sample_documents
from autoeval_sum.ingestion.persist import list_documents, save_documents

router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"])
log = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))


# ── Request / Response models ─────────────────────────────────────────────────

class PrepareRequest(BaseModel):
    seed: int = Field(default=42, description="RNG seed for deterministic sampling")
    corpus_size: int = Field(default=150, ge=100, le=200, description="Target corpus size")


class PrepareResponse(BaseModel):
    ingestion_id: str = Field(..., description="Seed used, acts as idempotency key")
    accepted_count: int
    status: str


class IngestionStatusResponse(BaseModel):
    total_documents: int
    difficulty_counts: dict[str, int]
    category_counts: dict[str, int]
    truncated_count: int


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "/prepare",
    response_model=PrepareResponse,
    status_code=status.HTTP_200_OK,
    summary="Prepare document corpus",
    description=(
        "Fetches MSMARCO passages, applies English + word-count filters, "
        "samples deterministically by seed, enriches with token counts / entity density "
        "/ difficulty / category, and persists to DynamoDB. Idempotent — safe to re-run."
    ),
    responses={
        422: {"model": ErrorDetail, "description": "Invalid corpus parameters"},
        500: {"model": ErrorDetail, "description": "Ingestion pipeline error"},
    },
)
async def prepare_ingestion(
    request: PrepareRequest,
    docs_db: DynamoDBClient = Depends(get_documents_db),
) -> PrepareResponse:
    settings = get_settings()
    corpus_dir = DATA_DIR / "corpus"

    try:
        # 1. Fetch raw passages (uses HF cache after first run)
        raw_docs = fetch_raw_documents(data_dir=DATA_DIR)

        # 2. Filter and sample
        filtered = filter_documents(raw_docs)
        sampled = sample_documents(
            filtered,
            corpus_size=request.corpus_size,
            seed=request.seed,
        )

        # 3. Enrich (LLM + spaCy)
        enriched = await enrich_documents(
            sampled,
            corpus_dir=corpus_dir,
            max_concurrency=settings.run_workers,
        )

        # 4. Persist to DynamoDB
        await save_documents(enriched, docs_db)

    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except RuntimeError as exc:
        log.exception("Ingestion failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        )

    return PrepareResponse(
        ingestion_id=str(request.seed),
        accepted_count=len(enriched),
        status="completed",
    )


@router.get(
    "/status",
    response_model=IngestionStatusResponse,
    summary="Get corpus status",
    description="Returns aggregate stats about the current Documents table contents.",
)
async def ingestion_status(
    docs_db: DynamoDBClient = Depends(get_documents_db),
) -> IngestionStatusResponse:
    docs: list[dict[str, Any]] = await list_documents(docs_db)

    difficulty_counts: dict[str, int] = {"easy": 0, "medium": 0, "hard": 0}
    category_counts: dict[str, int] = {}
    truncated_count = 0

    for doc in docs:
        tag = str(doc.get("difficulty_tag", "unknown"))
        difficulty_counts[tag] = difficulty_counts.get(tag, 0) + 1

        cat = str(doc.get("category_tag", "Unknown"))
        category_counts[cat] = category_counts.get(cat, 0) + 1

        if doc.get("was_truncated"):
            truncated_count += 1

    return IngestionStatusResponse(
        total_documents=len(docs),
        difficulty_counts=difficulty_counts,
        category_counts=category_counts,
        truncated_count=truncated_count,
    )
