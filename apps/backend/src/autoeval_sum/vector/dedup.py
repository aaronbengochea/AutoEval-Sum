"""
Eval prompt deduplication logic.

Checks whether a candidate eval case is semantically near-duplicate to any
existing eval prompt already stored in the ``eval_prompts`` Pinecone namespace.
Threshold: cosine similarity >= 0.90 → reject.
"""

import logging
from typing import Any

from autoeval_sum.vector.client import NS_EVAL_PROMPTS, PineconeClient

log = logging.getLogger(__name__)

DEDUP_THRESHOLD = 0.90


def _case_text(case: dict[str, Any]) -> str:
    """Build the text to embed for dedup comparison."""
    parts = [case.get("prompt_template", "")]
    note = case.get("rubric_note", "")
    if note:
        parts.append(note)
    return " ".join(parts).strip()


async def is_near_duplicate(
    prompt_text: str,
    client: PineconeClient,
) -> bool:
    """
    Return True if `prompt_text` is too similar to an existing eval prompt.

    Parameters
    ----------
    prompt_text:
        The candidate eval case text (prompt_template + rubric_note).
    client:
        Initialised PineconeClient.

    Returns
    -------
    bool
        True if top-1 similarity >= DEDUP_THRESHOLD (0.90).
    """
    try:
        matches = await client.query_similar(
            prompt_text,
            namespace=NS_EVAL_PROMPTS,
            top_k=1,
        )
    except Exception as exc:
        log.warning("Dedup query failed; treating as non-duplicate: %s", exc)
        return False

    if not matches:
        return False

    top_score: float = matches[0]["score"]
    if top_score >= DEDUP_THRESHOLD:
        log.debug("Dedup reject — top similarity %.4f >= %.2f", top_score, DEDUP_THRESHOLD)
        return True

    return False


async def filter_duplicates(
    cases: list[dict[str, Any]],
    client: PineconeClient,
) -> tuple[list[dict[str, Any]], int]:
    """
    Filter out near-duplicate eval cases from a candidate v2 suite.

    Parameters
    ----------
    cases:
        Serialised EvalCase list to filter.
    client:
        Initialised PineconeClient.

    Returns
    -------
    (accepted, rejected_count)
        accepted   — cases that passed the dedup check
        rejected_count — number of cases removed
    """
    accepted: list[dict[str, Any]] = []
    rejected = 0

    for case in cases:
        text = _case_text(case)
        if not text:
            accepted.append(case)
            continue

        duplicate = await is_near_duplicate(text, client)
        if duplicate:
            rejected += 1
            log.info(
                "Dedup: rejected case %s (too similar to existing prompts).",
                case.get("eval_id"),
            )
        else:
            accepted.append(case)

    if rejected:
        log.info("Dedup: %d/%d cases rejected from v2 suite.", rejected, len(cases))

    return accepted, rejected
