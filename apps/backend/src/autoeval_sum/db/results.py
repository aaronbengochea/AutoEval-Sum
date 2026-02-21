"""
Persistence layer for individual eval result records.

DynamoDB key layout for EvalResults
--------------------------------------
pk = suite_id  (format: {run_id}#v{n})
sk = eval_id   (format: v{n}-case-{0001})

Each record is one JudgeCaseResult for a single eval case in a single suite.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from autoeval_sum.db.client import DynamoDBClient

log = logging.getLogger(__name__)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


async def save_result(
    suite_id: str,
    eval_id: str,
    result: dict[str, Any],
    db: DynamoDBClient,
) -> None:
    """
    Persist a single JudgeCaseResult.

    Parameters
    ----------
    suite_id:
        Format: {run_id}#v{n}
    eval_id:
        Format: v{n}-case-{0001}
    result:
        Serialised JudgeCaseResult dict (includes scores, pass, tags, rationale).
    """
    item: dict[str, Any] = {
        "pk": suite_id,
        "sk": eval_id,
        "suite_id": suite_id,
        "eval_id": eval_id,
        "created_at": _now_utc(),
        **result,
    }
    await db.put_item(item)
    log.debug("Saved result %s / %s", suite_id, eval_id)


async def save_results_batch(
    suite_id: str,
    results: list[dict[str, Any]],
    db: DynamoDBClient,
) -> None:
    """Persist all judge results for a completed suite."""
    for r in results:
        eval_id = r.get("eval_id", "unknown")
        await save_result(suite_id, eval_id, r, db)
    log.info("Persisted %d results for suite %s", len(results), suite_id)


async def get_result(
    suite_id: str,
    eval_id: str,
    db: DynamoDBClient,
) -> dict[str, Any] | None:
    """Retrieve a single result by suite_id + eval_id."""
    return await db.get_item(pk=suite_id, sk=eval_id)


async def list_results_for_suite(
    suite_id: str,
    db: DynamoDBClient,
) -> list[dict[str, Any]]:
    """Return all results for a suite (full judge pass)."""
    return await db.query(pk=suite_id)
