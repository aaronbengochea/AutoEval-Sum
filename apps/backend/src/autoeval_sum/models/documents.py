from typing import Literal

from pydantic import BaseModel, Field


class RawDocument(BaseModel):
    """A passage extracted from the MSMARCO dataset before filtering/enrichment."""

    text: str
    url: str
    source_query_id: int


class EnrichedDocument(BaseModel):
    """A document that has passed all filters and been fully enriched."""

    doc_id: str = Field(..., description="UUIDv7 assigned at enrichment time")
    text: str
    url: str
    source_query_id: int

    # ── Corpus stats ──────────────────────────────────────────────────────────
    word_count: int
    token_count: int = Field(..., description="Token count from Gemini count_tokens")
    was_truncated: bool = Field(
        default=False,
        description="True if text was truncated to 2048 tokens for agent use",
    )

    # ── Enrichment ────────────────────────────────────────────────────────────
    entity_density: float = Field(..., ge=0.0, description="spaCy entity count / word count")
    difficulty_tag: Literal["easy", "medium", "hard"]
    category_tag: str

    # ── Storage ───────────────────────────────────────────────────────────────
    content_path: str = Field(..., description="Relative path to raw text file under data/")
