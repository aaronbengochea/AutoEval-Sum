import logging
from typing import Any

import aioboto3
import httpx
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pinecone import Pinecone

from autoeval_sum.config.settings import get_settings

router = APIRouter(tags=["health"])
log = logging.getLogger(__name__)


@router.get("/health")
async def liveness() -> dict[str, str]:
    """Liveness probe — service is running."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness() -> JSONResponse:
    """
    Readiness probe — checks live connectivity to DynamoDB and Pinecone.
    Returns 200 when all dependencies are reachable, 503 otherwise.
    """
    settings = get_settings()
    checks: dict[str, Any] = {}
    healthy = True

    # ── DynamoDB ──────────────────────────────────────────────────────────────
    try:
        session = aioboto3.Session()
        async with session.client(
            "dynamodb",
            region_name=settings.aws_region,
            endpoint_url=settings.dynamodb_endpoint_url,
            aws_access_key_id="local",
            aws_secret_access_key="local",
        ) as client:
            await client.list_tables(Limit=1)
        checks["dynamodb"] = "ok"
    except Exception as exc:
        log.warning("DynamoDB readiness check failed: %s", exc)
        checks["dynamodb"] = f"error: {exc}"
        healthy = False

    # ── Pinecone ──────────────────────────────────────────────────────────────
    try:
        pc = Pinecone(api_key=settings.pinecone_api_key)
        # list_indexes() is a lightweight connectivity probe
        pc.list_indexes()
        checks["pinecone"] = "ok"
    except Exception as exc:
        log.warning("Pinecone readiness check failed: %s", exc)
        checks["pinecone"] = f"error: {exc}"
        healthy = False

    http_status = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=http_status,
        content={"status": "ready" if healthy else "not_ready", "checks": checks},
    )
