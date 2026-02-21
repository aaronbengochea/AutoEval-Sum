"""
load_docs node — loads all enriched document records from DynamoDB.
"""

import logging
from typing import Any

from autoeval_sum.db.client import DynamoDBClient
from autoeval_sum.ingestion.persist import list_documents
from autoeval_sum.runtime.state import RunState

log = logging.getLogger(__name__)


def make_load_docs_node(
    docs_db: DynamoDBClient,
) -> Any:
    """Return the load_docs node function with injected DynamoDB client."""

    async def load_docs(state: RunState) -> dict:  # type: ignore[type-arg]
        items = await list_documents(docs_db)
        log.info("Loaded %d document records from DynamoDB.", len(items))
        if not items:
            log.error("No documents found in corpus. Run POST /api/v1/ingestion/prepare first.")
            return {
                "docs": [],
                "errors": ["Corpus is empty — run ingestion before starting an eval run."],
            }
        return {"docs": items}

    return load_docs
