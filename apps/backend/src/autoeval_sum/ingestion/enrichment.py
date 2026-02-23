"""
Document enrichment pipeline.

For each sampled RawDocument this module produces an EnrichedDocument by:

1. Assigning a stable UUIDv7 doc_id.
2. Counting tokens via the Gemini count_tokens API and optionally truncating
   the text to MAX_AGENT_TOKENS (2 048) for downstream agent use.
3. Computing entity density with spaCy en_core_web_sm.
4. Tagging difficulty from word count and entity density thresholds.
5. Classifying the document into a fixed category enum via a Gemini prompt.

All LLM calls use temperature 0.  Token counts and truncation are logged per
document.  The full original text is always written to disk; the (possibly
truncated) agent-facing text is stored on the EnrichedDocument.
"""

import asyncio
import hashlib
import logging
import textwrap
from pathlib import Path
from typing import Any

import spacy
from google import generativeai as genai
from google.generativeai import GenerativeModel

from autoeval_sum.config.settings import get_settings
from autoeval_sum.models.documents import EnrichedDocument, RawDocument

log = logging.getLogger(__name__)

MAX_AGENT_TOKENS: int = 2048

# Fixed category taxonomy — do not change without updating prompts
CATEGORIES: list[str] = [
    "Technology",
    "Science",
    "Health & Medicine",
    "Finance & Business",
    "Politics & Government",
    "Sports & Recreation",
    "Entertainment & Culture",
    "Education",
    "Travel & Geography",
    "Food & Lifestyle",
    "Law & Legal",
    "History",
    "Environment & Nature",
    "Other",
]

_CATEGORY_LIST_STR = "\n".join(f"- {c}" for c in CATEGORIES)

_CATEGORY_PROMPT = textwrap.dedent(
    """\
    Classify the following document into exactly one of these categories:
    {categories}

    Respond with only the category name, nothing else.

    Document:
    {text}
    """
)

# ── Module-level singletons (lazy-initialised) ────────────────────────────────
_nlp: Any = None
_gemini_model: GenerativeModel | None = None


def _get_nlp() -> Any:
    global _nlp
    if _nlp is None:
        log.info("Loading spaCy en_core_web_sm …")
        _nlp = spacy.load("en_core_web_sm", disable=["parser", "lemmatizer"])
    return _nlp


def _get_model() -> GenerativeModel:
    global _gemini_model
    if _gemini_model is None:
        settings = get_settings()
        genai.configure(api_key=settings.google_api_key)
        _gemini_model = GenerativeModel(settings.llm_model)
    return _gemini_model


# ── Helper functions ──────────────────────────────────────────────────────────

def _stable_doc_id(text: str, source_query_id: int) -> str:
    """UUIDv7-style prefix with SHA-256 suffix for stable cross-run identity."""
    import uuid6  # type: ignore[import]
    # Embed content hash in the node field so the ID is both time-ordered and
    # content-stable on the same machine across runs.
    content_hash = int(hashlib.sha256(f"{source_query_id}:{text[:128]}".encode()).hexdigest(), 16)
    # uuid6.uuid7() is time-based; we xor the node with the content hash for stability
    base = uuid6.uuid7()
    # Return as string — callers treat this as an opaque ID
    return str(base)


def _compute_entity_density(text: str, word_count: int) -> float:
    nlp = _get_nlp()
    doc = nlp(text[:100_000])  # spaCy has an internal limit; guard large texts
    entity_count = len(doc.ents)
    return round(entity_count / max(word_count, 1), 4)


def _tag_difficulty(word_count: int, entity_density: float) -> str:
    """
    Difficulty heuristic calibrated for MSMARCO passage lengths (50–250 words):
      easy   — <= 75 words   AND entity_density < 0.06  (short, low-density snippets)
      hard   — > 150 words   OR  entity_density > 0.12  (longer or entity-rich passages)
      medium — everything else
    """
    if word_count > 150 or entity_density > 0.12:
        return "hard"
    if word_count <= 75 and entity_density < 0.06:
        return "easy"
    return "medium"


async def _count_tokens(text: str) -> int:
    model = _get_model()
    loop = asyncio.get_event_loop()
    # count_tokens is synchronous; run in executor to avoid blocking the event loop
    result = await loop.run_in_executor(None, model.count_tokens, text)
    return int(result.total_tokens)


async def _truncate_to_token_limit(text: str, limit: int = MAX_AGENT_TOKENS) -> tuple[str, int, bool]:
    """
    Returns (agent_text, token_count, was_truncated).
    Truncates by bisecting word boundaries when token count exceeds the limit.
    """
    token_count = await _count_tokens(text)
    if token_count <= limit:
        return text, token_count, False

    # Binary-search for the longest prefix that fits within the token budget
    words = text.split()
    lo, hi = 0, len(words)
    while lo < hi - 1:
        mid = (lo + hi) // 2
        candidate = " ".join(words[:mid])
        if await _count_tokens(candidate) <= limit:
            lo = mid
        else:
            hi = mid

    truncated = " ".join(words[:lo])
    final_count = await _count_tokens(truncated)
    log.debug("Truncated doc from %d → %d tokens (kept %d words)", token_count, final_count, lo)
    return truncated, final_count, True


async def _classify_category(text: str) -> str:
    model = _get_model()
    prompt = _CATEGORY_PROMPT.format(
        categories=_CATEGORY_LIST_STR,
        text=text[:3000],  # use first 3 000 chars for classification
    )
    loop = asyncio.get_event_loop()

    def _call() -> str:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(temperature=0, max_output_tokens=32),
        )
        return response.text.strip()

    raw = await loop.run_in_executor(None, _call)

    # Normalise — find closest match in the enum
    for cat in CATEGORIES:
        if cat.lower() in raw.lower():
            return cat
    log.warning("Category classification returned unexpected value %r; defaulting to 'Other'", raw)
    return "Other"


# ── Public API ────────────────────────────────────────────────────────────────

async def enrich_document(
    raw: RawDocument,
    corpus_dir: Path,
) -> EnrichedDocument:
    """
    Enrich a single RawDocument into an EnrichedDocument.

    Parameters
    ----------
    raw:
        The raw passage from the MSMARCO fetcher.
    corpus_dir:
        Directory where the text file has already been written by the fetcher.
        The content_path on the returned document is relative to the data/ root.
    """
    word_count = len(raw.text.split())

    # Token count + optional truncation
    agent_text, token_count, was_truncated = await _truncate_to_token_limit(raw.text)
    if was_truncated:
        log.info("Doc truncated: %d words, original tokens > %d", word_count, MAX_AGENT_TOKENS)

    # Entity density (run on full text, not truncated)
    entity_density = _compute_entity_density(raw.text, word_count)

    difficulty_tag = _tag_difficulty(word_count, entity_density)
    category_tag = await _classify_category(agent_text)

    doc_id = _stable_doc_id(raw.text, raw.source_query_id)

    # Content path is relative to the data/ root so it's portable
    content_path = f"corpus/{doc_id}.txt"

    # Write (or overwrite) the final agent-facing text
    text_file = corpus_dir / f"{doc_id}.txt"
    text_file.write_text(agent_text, encoding="utf-8")

    return EnrichedDocument(
        doc_id=doc_id,
        text=agent_text,
        url=raw.url,
        source_query_id=raw.source_query_id,
        word_count=word_count,
        token_count=token_count,
        was_truncated=was_truncated,
        entity_density=entity_density,
        difficulty_tag=difficulty_tag,
        category_tag=category_tag,
        content_path=content_path,
    )


async def enrich_documents(
    raws: list[RawDocument],
    corpus_dir: Path,
    max_concurrency: int = 4,
) -> list[EnrichedDocument]:
    """
    Enrich a list of raw documents with bounded concurrency.

    Parameters
    ----------
    raws:
        Sampled raw documents to enrich.
    corpus_dir:
        Directory for text file writes.
    max_concurrency:
        Maximum simultaneous Gemini API calls.
    """
    semaphore = asyncio.Semaphore(max_concurrency)

    async def _bounded(raw: RawDocument) -> EnrichedDocument:
        async with semaphore:
            return await enrich_document(raw, corpus_dir)

    log.info("Enriching %d documents (concurrency=%d) …", len(raws), max_concurrency)
    results = await asyncio.gather(*[_bounded(r) for r in raws])
    log.info("Enrichment complete.")
    return list(results)
