from fastapi import FastAPI

from autoeval_sum.config.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="AutoEval-Sum",
        version="0.1.0",
        description="Autonomous evaluation suite improvement system for summarization testing",
        debug=settings.debug,
    )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
