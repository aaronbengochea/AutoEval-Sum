from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "autoeval-sum"
    debug: bool = False
    log_level: str = "INFO"

    # ── Google / Gemini ───────────────────────────────────────────────────────
    google_api_key: str = Field(..., description="Google API key for Gemini and embeddings")
    llm_model: str = Field(default="gemini-2.0-flash", description="Gemini model ID")
    embedding_model: str = Field(
        default="text-embedding-004", description="Google embedding model ID"
    )

    # ── Pinecone ──────────────────────────────────────────────────────────────
    pinecone_api_key: str = Field(..., description="Pinecone API key")
    pinecone_index_name: str = Field(default="autoeval-sum", description="Pinecone index name")
    pinecone_environment: str = Field(default="us-east-1", description="Pinecone cloud region")
    pinecone_cloud: str = Field(default="aws", description="Pinecone serverless cloud provider")
    pinecone_metric: str = Field(default="cosine", description="Pinecone index distance metric")
    pinecone_embedding_dimension: int = Field(
        default=768, description="Embedding dimension for text-embedding-004"
    )

    # ── DynamoDB ──────────────────────────────────────────────────────────────
    aws_region: str = Field(default="us-east-1", description="AWS region")
    dynamodb_endpoint_url: str = Field(
        default="http://dynamodb-local:8000",
        description="DynamoDB endpoint (local or AWS)",
    )
    dynamodb_runs_table: str = Field(default="AutoEvalRuns")
    dynamodb_documents_table: str = Field(default="Documents")
    dynamodb_suites_table: str = Field(default="EvalSuites")
    dynamodb_results_table: str = Field(default="EvalResults")

    # ── Run defaults ──────────────────────────────────────────────────────────
    default_seed: int = Field(default=42, description="Default RNG seed")
    default_corpus_size: int = Field(default=150, ge=100, le=200)
    default_suite_size: int = Field(default=20, ge=1)
    max_token_budget: int = Field(default=300_000, description="Per-run token cap")
    run_workers: int = Field(default=4, description="Bounded parallelism per suite")


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance. Fails fast on missing required vars."""
    return Settings()
