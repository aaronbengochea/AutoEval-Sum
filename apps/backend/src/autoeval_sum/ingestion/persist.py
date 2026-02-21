"""
Persistence layer for enriched documents.

Writes each EnrichedDocument to the DynamoDB Documents table.
The raw text file is already on disk (written by fetcher/enrichment);
this module only handles the metadata record.

DynamoDB key layout for Documents
----------------------------------
pk = doc_id  (no sort key — each document is a standalone entity)
"""

import logging
from datetime import datetime, timezone

from autoeval_sum.db.client import DynamoDBClient
from autoeval_sum.models.documents import EnrichedDocument

log = logging.getLogger(__name__)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


async def save_document(doc: EnrichedDocument, db: DynamoDBClient) -> None:
    """Persist a single EnrichedDocument to DynamoDB."""
    item = {
        "pk": doc.doc_id,
        "doc_id": doc.doc_id,
        "url": doc.url,
        "source_query_id": doc.source_query_id,
        "word_count": doc.word_count,
        "token_count": doc.token_count,
        "was_truncated": doc.was_truncated,
        "entity_density": doc.entity_density,
        "difficulty_tag": doc.difficulty_tag,
        "category_tag": doc.category_tag,
        "content_path": doc.content_path,
        "created_at": _now_utc(),
    }
    await db.put_item(item)
    log.debug("Saved document %s (%s / %s)", doc.doc_id, doc.difficulty_tag, doc.category_tag)


async def save_documents(docs: list[EnrichedDocument], db: DynamoDBClient) -> None:
    """Persist a batch of EnrichedDocuments."""
    for doc in docs:
        await save_document(doc, db)
    log.info("Persisted %d documents to DynamoDB.", len(docs))


async def get_document(doc_id: str, db: DynamoDBClient) -> dict | None:
    """Retrieve a document record by doc_id."""
    return await db.get_item(pk=doc_id)


async def list_documents(db: DynamoDBClient) -> list[dict]:
    """Return all document records (full table scan — only for admin/status use)."""
    return await db.scan_all()
