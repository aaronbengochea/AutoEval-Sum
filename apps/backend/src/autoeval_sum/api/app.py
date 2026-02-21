from fastapi import FastAPI

from autoeval_sum.api.routes.health import router as health_router
from autoeval_sum.api.routes.ingestion import router as ingestion_router
from autoeval_sum.config.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="AutoEval-Sum",
        version="0.1.0",
        description="Autonomous evaluation suite improvement system for summarization testing",
        debug=settings.debug,
    )

    app.include_router(health_router)
    app.include_router(ingestion_router)

    return app
