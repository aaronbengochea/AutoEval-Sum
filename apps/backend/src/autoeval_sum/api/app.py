import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from autoeval_sum.api.routes.health import router as health_router
from autoeval_sum.api.routes.ingestion import router as ingestion_router
from autoeval_sum.config.settings import get_settings
from autoeval_sum.db.client import DynamoDBClient
from autoeval_sum.db.runs import mark_stale_runs_failed

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Startup: mark any in-progress runs as failed (orphaned by a previous crash).
    Shutdown: nothing to clean up (queue is in-process, DB connections are per-call).
    """
    settings = get_settings()
    runs_db = DynamoDBClient(
        table_name=settings.dynamodb_runs_table,
        region=settings.aws_region,
        endpoint_url=settings.dynamodb_endpoint_url,
    )
    stale = await mark_stale_runs_failed(runs_db)
    if stale:
        log.warning("Startup: marked %d orphaned run(s) as failed.", stale)
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="AutoEval-Sum",
        version="0.1.0",
        description="Autonomous evaluation suite improvement system for summarization testing",
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.include_router(health_router)
    app.include_router(ingestion_router)

    return app
