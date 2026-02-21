"""
Pinecone failure memory — read/write paths for targeted v2 generation.

Two operations:
1. upsert_eval_prompts  — index v1 eval cases into eval_prompts namespace so
                          future dedup checks can compare against them.
2. store_failures       — index failing judge results into failures namespace
                          so the curriculum can retrieve failure exemplars.
3. retrieve_failure_exemplars — query failures namespace and return formatted
                          strings the curriculum agent can reason about.
"""

import logging
from typing import Any

from autoeval_sum.vector.client import NS_EVAL_PROMPTS, NS_FAILURES, PineconeClient

log = logging.getLogger(__name__)


def _eval_case_text(case: dict[str, Any]) -> str:
    """Build the embedding text for an eval case."""
    parts = [case.get("prompt_template", "")]
    note = case.get("rubric_note", "")
    if note:
        parts.append(note)
    return " ".join(parts).strip()


def _failure_text(result: dict[str, Any]) -> str:
    """Build the embedding text for a failure record."""
    tags = ", ".join(result.get("failure_tags", []))
    rationale = result.get("rationale", "")
    return f"Failure tags: {tags}. Rationale: {rationale}".strip()


async def upsert_eval_prompts(
    eval_suite: list[dict[str, Any]],
    run_id: str,
    suite_version: str,
    client: PineconeClient,
) -> None:
    """
    Upsert all eval cases from a suite into the eval_prompts namespace.

    Called after eval_author generates each suite so future dedup checks
    can compare v2 candidates against v1 prompts already indexed.

    Parameters
    ----------
    eval_suite:
        Serialised EvalCase list.
    run_id:
        Run identifier (stored in metadata for traceability).
    suite_version:
        "v1" or "v2" (stored in metadata).
    client:
        Initialised PineconeClient.
    """
    if not eval_suite:
        return

    items = [
        {
            "id": f"{run_id}#{suite_version}#{case['eval_id']}",
            "text": _eval_case_text(case),
            "eval_id": case.get("eval_id", ""),
            "doc_id": case.get("doc_id", ""),
            "run_id": run_id,
            "suite_version": suite_version,
            "difficulty_tag": case.get("difficulty_tag", ""),
            "category_tag": case.get("category_tag", ""),
        }
        for case in eval_suite
        if _eval_case_text(case)
    ]

    if not items:
        return

    try:
        await client.embed_and_upsert(items, namespace=NS_EVAL_PROMPTS)
        log.info(
            "Upserted %d eval prompts (run=%s, suite=%s) to Pinecone.",
            len(items), run_id, suite_version,
        )
    except Exception as exc:
        log.error("Failed to upsert eval prompts to Pinecone: %s", exc)


async def store_failures(
    judge_results: list[dict[str, Any]],
    eval_suite: list[dict[str, Any]],
    run_id: str,
    suite_version: str,
    client: PineconeClient,
) -> None:
    """
    Index failing judge results into the failures namespace.

    Only results where pass=False are indexed.  The embedding text combines
    failure tags and rationale so queries can surface thematically similar
    past failures.

    Parameters
    ----------
    judge_results:
        Serialised JudgeCaseResult list.
    eval_suite:
        Serialised EvalCase list (for difficulty/category metadata).
    run_id:
        Run identifier.
    suite_version:
        "v1" or "v2".
    client:
        Initialised PineconeClient.
    """
    suite_by_id = {c["eval_id"]: c for c in eval_suite}
    failing = [r for r in judge_results if not r.get("pass", True)]

    if not failing:
        log.debug("No failing results to store for run %s %s.", run_id, suite_version)
        return

    items = []
    for r in failing:
        eval_id = r.get("eval_id", "")
        text = _failure_text(r)
        if not text:
            continue

        case = suite_by_id.get(eval_id, {})
        items.append({
            "id": f"{run_id}#{suite_version}#{eval_id}#fail",
            "text": text,
            "eval_id": eval_id,
            "run_id": run_id,
            "suite_version": suite_version,
            "failure_tags": ", ".join(r.get("failure_tags", [])),
            "aggregate_score": str(r.get("aggregate_score", 0.0)),
            "difficulty_tag": case.get("difficulty_tag", ""),
            "category_tag": case.get("category_tag", ""),
        })

    if not items:
        return

    try:
        await client.embed_and_upsert(items, namespace=NS_FAILURES)
        log.info(
            "Stored %d failure records (run=%s, suite=%s) in Pinecone.",
            len(items), run_id, suite_version,
        )
    except Exception as exc:
        log.error("Failed to store failures in Pinecone: %s", exc)


async def retrieve_failure_exemplars(
    failure_tags: list[str],
    client: PineconeClient,
    top_k: int = 10,
) -> list[str]:
    """
    Query the failures namespace for exemplars matching the given failure tags.

    Returns a list of human-readable strings the curriculum agent can include
    in its prompt context to guide targeted v2 case generation.

    Parameters
    ----------
    failure_tags:
        Top failure tags from the v1 suite (e.g. ["hallucinated_fact", "poor_structure"]).
    client:
        Initialised PineconeClient.
    top_k:
        Maximum exemplars to retrieve.
    """
    if not failure_tags:
        return []

    query_text = f"Failure tags: {', '.join(failure_tags)}"

    try:
        matches = await client.query_similar(
            query_text,
            namespace=NS_FAILURES,
            top_k=top_k,
        )
    except Exception as exc:
        log.warning("Failed to retrieve failure exemplars from Pinecone: %s", exc)
        return []

    exemplars: list[str] = []
    for match in matches:
        meta = match.get("metadata", {})
        tags = meta.get("failure_tags", "")
        score = match.get("score", 0.0)
        diff = meta.get("difficulty_tag", "")
        cat = meta.get("category_tag", "")
        exemplars.append(
            f"[score={score:.2f}] {tags}"
            + (f" | difficulty={diff}" if diff else "")
            + (f" | category={cat}" if cat else "")
        )

    log.debug("Retrieved %d failure exemplars for tags: %s", len(exemplars), failure_tags[:3])
    return exemplars
