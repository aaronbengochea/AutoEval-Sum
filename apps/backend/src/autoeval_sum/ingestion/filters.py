"""
Deterministic filtering and sampling pipeline.

Filters
-------
1. English-language check  — text must be >= 90% printable ASCII characters.
   MS MARCO is an English corpus; this guards against encoding artifacts.
2. Minimum word count     — text must have >= 500 whitespace-separated tokens.

Sampling
--------
After filtering, the remaining pool is shuffled with Python's built-in
``random.Random(seed)`` and the first ``corpus_size`` documents are returned.
Using a fixed seed produces an identical ordered subset on every run,
satisfying the determinism requirement (Acceptance Scenario D).
"""

import logging
import random
import string

from autoeval_sum.models.documents import RawDocument

log = logging.getLogger(__name__)

MIN_WORD_COUNT: int = 500
MIN_ASCII_RATIO: float = 0.90


def _word_count(text: str) -> int:
    return len(text.split())


def _ascii_ratio(text: str) -> float:
    if not text:
        return 0.0
    printable = set(string.printable)
    return sum(1 for ch in text if ch in printable) / len(text)


def _is_english(text: str) -> bool:
    return _ascii_ratio(text) >= MIN_ASCII_RATIO


def filter_documents(docs: list[RawDocument]) -> list[RawDocument]:
    """
    Apply English and minimum-word-count filters.

    Returns the subset of ``docs`` that passes both checks, preserving
    original order so downstream seeded sampling is deterministic given
    a stable input pool.
    """
    passed: list[RawDocument] = []
    rejected_lang = 0
    rejected_len = 0

    for doc in docs:
        if not _is_english(doc.text):
            rejected_lang += 1
            continue
        if _word_count(doc.text) < MIN_WORD_COUNT:
            rejected_len += 1
            continue
        passed.append(doc)

    log.info(
        "Filter: %d passed  |  %d rejected (language)  |  %d rejected (word count < %d)",
        len(passed),
        rejected_lang,
        rejected_len,
        MIN_WORD_COUNT,
    )
    return passed


def sample_documents(
    docs: list[RawDocument],
    corpus_size: int,
    seed: int,
) -> list[RawDocument]:
    """
    Deterministically sample ``corpus_size`` documents from the filtered pool.

    Parameters
    ----------
    docs:
        Pre-filtered document pool (output of ``filter_documents``).
    corpus_size:
        Number of documents to return.  Must be in range [100, 200].
    seed:
        RNG seed.  Same seed always produces the same ordered subset.

    Raises
    ------
    ValueError
        If the filtered pool is smaller than ``corpus_size``.
    """
    if len(docs) < corpus_size:
        raise ValueError(
            f"Filtered pool has only {len(docs)} documents but corpus_size={corpus_size} "
            f"was requested.  Increase MSMARCO_SCAN_LIMIT or relax filters."
        )

    rng = random.Random(seed)
    pool = list(docs)
    rng.shuffle(pool)
    sampled = pool[:corpus_size]

    log.info(
        "Sampled %d documents from pool of %d  (seed=%d)",
        len(sampled),
        len(docs),
        seed,
    )
    return sampled
