"""
Idempotent corpus ingestion setup.

Fetches MSMARCO passages from HuggingFace, applies English/length filters,
samples deterministically, enriches each document with Gemini (token counts,
entity density, difficulty, category), and persists metadata to DynamoDB.

Safe to run repeatedly — if the Documents table already contains records the
script exits immediately without making any network calls.

Usage:
    uv run python scripts/setup_corpus.py
    # or inside compose via setup-corpus service
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from autoeval_sum.config.settings import get_settings
from autoeval_sum.db.client import DynamoDBClient
from autoeval_sum.ingestion.enrichment import enrich_documents
from autoeval_sum.ingestion.fetcher import fetch_raw_documents
from autoeval_sum.ingestion.filters import filter_documents, sample_documents
from autoeval_sum.ingestion.persist import list_documents, save_documents

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))


async def setup_corpus() -> None:
    settings = get_settings()

    docs_db = DynamoDBClient(
        table_name=settings.dynamodb_documents_table,
        region=settings.aws_region,
        endpoint_url=settings.dynamodb_endpoint_url,
    )

    # Idempotency check — skip everything if corpus already populated
    existing = await list_documents(docs_db)
    if existing:
        log.info(
            "Documents table already has %d records — skipping ingestion.",
            len(existing),
        )
        return

    log.info(
        "Starting corpus ingestion (seed=%d, size=%d) …",
        settings.default_seed,
        settings.default_corpus_size,
    )

    corpus_dir = DATA_DIR / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)

    # 1. Fetch raw passages from MSMARCO (uses HF cache after first run)
    raw_docs = fetch_raw_documents(data_dir=DATA_DIR)

    # 2. Filter (English + min word count) and deterministic sample
    filtered = filter_documents(raw_docs)
    sampled = sample_documents(
        filtered,
        corpus_size=settings.default_corpus_size,
        seed=settings.default_seed,
    )

    # 3. Enrich with Gemini (token counts, entity density, difficulty, category)
    enriched = await enrich_documents(
        sampled,
        corpus_dir=corpus_dir,
        max_concurrency=settings.run_workers,
    )

    # 4. Persist metadata records to DynamoDB
    await save_documents(enriched, docs_db)

    log.info("Corpus ingestion complete — %d documents persisted.", len(enriched))


if __name__ == "__main__":
    try:
        asyncio.run(setup_corpus())
    except Exception as exc:
        log.error("Corpus setup failed: %s", exc)
        sys.exit(1)
