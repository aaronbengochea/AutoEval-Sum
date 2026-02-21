"""
Idempotent Pinecone index setup.

Creates the autoeval-sum index if it does not already exist.
Namespaces (eval_prompts, failures) are created automatically on first
upsert — no explicit creation needed. This script verifies connectivity
and documents the expected namespaces.

Safe to run repeatedly — existing index is left untouched.

Usage:
    uv run python scripts/setup_pinecone.py
    # or inside compose via setup-pinecone service
"""

import logging
import os
import sys
import time

from pinecone import Pinecone, ServerlessSpec

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "autoeval-sum")
CLOUD = os.getenv("PINECONE_CLOUD", "aws")
REGION = os.getenv("PINECONE_ENVIRONMENT", "us-east-1")
EMBEDDING_DIMENSION = int(os.getenv("PINECONE_EMBEDDING_DIMENSION", "768"))
METRIC = os.getenv("PINECONE_METRIC", "cosine")

# Namespaces — documented here; created automatically on first upsert
NAMESPACES = ["eval_prompts", "failures"]


def setup_index() -> None:
    if not PINECONE_API_KEY:
        raise EnvironmentError(
            "PINECONE_API_KEY is not set. "
            "Add it to your .env file before running setup."
        )

    pc = Pinecone(api_key=PINECONE_API_KEY)

    existing = [idx.name for idx in pc.list_indexes()]
    log.info("Existing Pinecone indexes: %s", existing or "(none)")

    if INDEX_NAME in existing:
        log.info("  ✓ Index '%s' already exists — skipping creation.", INDEX_NAME)
    else:
        log.info(
            "  + Creating index '%s' (dim=%d, metric=%s, cloud=%s, region=%s) …",
            INDEX_NAME,
            EMBEDDING_DIMENSION,
            METRIC,
            CLOUD,
            REGION,
        )
        pc.create_index(
            name=INDEX_NAME,
            dimension=EMBEDDING_DIMENSION,
            metric=METRIC,
            spec=ServerlessSpec(cloud=CLOUD, region=REGION),
        )

        # Wait until the index is ready
        for attempt in range(30):
            desc = pc.describe_index(INDEX_NAME)
            if desc.status.get("ready", False):
                break
            log.info("    … waiting for index to become ready (attempt %d/30)", attempt + 1)
            time.sleep(5)
        else:
            raise TimeoutError(f"Index '{INDEX_NAME}' did not become ready in time.")

        log.info("  ✓ Index '%s' is ready.", INDEX_NAME)

    # Verify connectivity by describing the index
    desc = pc.describe_index(INDEX_NAME)
    log.info(
        "  Index status: ready=%s, host=%s",
        desc.status.get("ready"),
        desc.host,
    )

    log.info(
        "  Namespaces %s will be created automatically on first upsert.",
        NAMESPACES,
    )
    log.info("Done.")


if __name__ == "__main__":
    try:
        setup_index()
    except Exception as exc:
        log.error("Pinecone setup failed: %s", exc)
        sys.exit(1)
