"""
Persistence layer for eval suite records.

DynamoDB key layout for EvalSuites
--------------------------------------
pk = run_id
sk = suite_version  (e.g. "v1", "v2")

A suite record stores the SuiteMetrics snapshot produced at the end of each
judge pass.  The raw EvalCase list is NOT stored here — it lives in memory
during the run and is exported to artifacts in Phase 9.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from autoeval_sum.db.client import DynamoDBClient

log = logging.getLogger(__name__)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


async def save_suite(
    run_id: str,
    suite_version: str,
    metrics: dict[str, Any],
    db: DynamoDBClient,
) -> None:
    """
    Persist suite metrics for one iteration of a run.

    Parameters
    ----------
    run_id:
        UUIDv7 run identifier.
    suite_version:
        Iteration tag — "v1" or "v2".
    metrics:
        Serialised SuiteMetrics dict.
    """
    item: dict[str, Any] = {
        "pk": run_id,
        "sk": suite_version,
        "run_id": run_id,
        "suite_version": suite_version,
        "suite_id": f"{run_id}#{suite_version}",
        "metrics": metrics,
        "created_at": _now_utc(),
    }
    await db.put_item(item)
    log.debug("Saved suite %s#%s", run_id, suite_version)


async def get_suite(
    run_id: str,
    suite_version: str,
    db: DynamoDBClient,
) -> dict[str, Any] | None:
    """Retrieve a suite record by run_id + suite_version."""
    return await db.get_item(pk=run_id, sk=suite_version)


async def list_suites_for_run(
    run_id: str,
    db: DynamoDBClient,
) -> list[dict[str, Any]]:
    """Return all suite records for a run (v1 + v2)."""
    return await db.query(pk=run_id)
