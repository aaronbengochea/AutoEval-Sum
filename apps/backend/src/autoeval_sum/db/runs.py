"""
Persistence layer for run records.

DynamoDB key layout for AutoEvalRuns
--------------------------------------
pk = run_id  (no sort key)
"""

import logging
from datetime import datetime, timezone
from typing import Any

from autoeval_sum.db.client import DynamoDBClient
from autoeval_sum.models.runs import RunRecord, RunStatus

log = logging.getLogger(__name__)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


async def save_run(run: RunRecord, db: DynamoDBClient) -> None:
    """Persist a new run record."""
    await db.put_item(run.to_dynamo_item())
    log.debug("Saved run %s (status=%s)", run.run_id, run.status.value)


async def get_run(run_id: str, db: DynamoDBClient) -> RunRecord | None:
    """Fetch a run by run_id. Returns None if not found."""
    item = await db.get_item(pk=run_id)
    if item is None:
        return None
    return RunRecord.from_dynamo_item(item)


async def update_run_status(
    run_id: str,
    status: RunStatus,
    db: DynamoDBClient,
    *,
    error_message: str | None = None,
    metrics_v1: dict[str, Any] | None = None,
    metrics_v2: dict[str, Any] | None = None,
) -> None:
    """Partial-update run status and optional timestamp/error fields."""
    updates: dict[str, Any] = {"status": status.value}

    if status == RunStatus.running:
        updates["started_at"] = _now_utc()
    elif status in (
        RunStatus.completed,
        RunStatus.completed_with_errors,
        RunStatus.failed,
    ):
        updates["completed_at"] = _now_utc()

    if error_message is not None:
        updates["error_message"] = error_message
    if metrics_v1 is not None:
        updates["metrics_v1"] = metrics_v1
    if metrics_v2 is not None:
        updates["metrics_v2"] = metrics_v2

    await db.update_item(pk=run_id, sk=None, updates=updates)
    log.info("Run %s → %s", run_id, status.value)


async def list_runs(db: DynamoDBClient) -> list[RunRecord]:
    """Return all run records (full scan — admin/status use only)."""
    items = await db.scan_all()
    return [RunRecord.from_dynamo_item(item) for item in items]


async def mark_stale_runs_failed(db: DynamoDBClient) -> int:
    """
    On process restart any run still in `running` status is orphaned.
    Mark them as failed so the queue can accept new work.
    Returns the count of affected runs.
    """
    runs = await list_runs(db)
    count = 0
    for run in runs:
        if run.status == RunStatus.running:
            await update_run_status(
                run.run_id,
                RunStatus.failed,
                db,
                error_message="Process restarted while run was in progress.",
            )
            count += 1
    if count:
        log.warning("Marked %d stale in-progress run(s) as failed on startup.", count)
    return count
