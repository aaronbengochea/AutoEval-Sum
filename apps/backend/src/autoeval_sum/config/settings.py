from functools import lru_cache

from pydantic import Field, model_validator
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
    data_dir: str = Field(default="data", description="Root directory for corpus text files")

    # ── Google / Gemini ───────────────────────────────────────────────────────
    google_api_key: str = Field(..., description="Google API key for Gemini and embeddings")
    llm_model: str = Field(default="gemini-2.0-flash", description="Gemini model ID")
    embedding_model: str = Field(
        default="gemini-embedding-001", description="Google embedding model ID"
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
    default_seed: int = Field(..., description="Default RNG seed")
    corpus_size_min: int = Field(..., ge=1, description="Minimum allowed corpus size")
    corpus_size_max: int = Field(..., ge=1, description="Maximum allowed corpus size")
    default_corpus_size: int = Field(..., description="Default corpus size for ingestion")
    default_suite_size: int = Field(..., ge=1, description="Default eval suite size")
    max_token_budget: int = Field(..., description="Per-run token cap")
    run_workers: int = Field(..., description="Bounded parallelism per suite")

    @model_validator(mode="after")
    def validate_corpus_size_bounds(self) -> "Settings":
        if not (self.corpus_size_min <= self.default_corpus_size <= self.corpus_size_max):
            raise ValueError(
                f"default_corpus_size={self.default_corpus_size} must be between "
                f"corpus_size_min={self.corpus_size_min} and corpus_size_max={self.corpus_size_max}"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance. Fails fast on missing required vars."""
    return Settings()
