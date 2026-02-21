"""
finalize node — persists the final run status and metrics to DynamoDB.
"""

import logging
from typing import Any

from autoeval_sum.db.client import DynamoDBClient
from autoeval_sum.db.runs import update_run_status
from autoeval_sum.models.runs import RunStatus
from autoeval_sum.runtime.queue import get_run_queue
from autoeval_sum.runtime.state import RunState

log = logging.getLogger(__name__)


def make_finalize_node(runs_db: DynamoDBClient) -> Any:
    """Return the finalize node with injected DynamoDB client."""

    async def finalize(state: RunState) -> dict:  # type: ignore[type-arg]
        run_id: str = state.get("run_id", "unknown")
        errors: list[str] = state.get("errors", [])
        metrics_v1 = state.get("metrics_v1")
        metrics_v2 = state.get("metrics_v2")

        # Determine terminal status
        if get_run_queue().check_cancel():
            final_status = RunStatus.failed
            log.info("Run %s: finalising as failed (cancel requested).", run_id)
        elif errors:
            final_status = RunStatus.completed_with_errors
            log.info(
                "Run %s: finalising as completed_with_errors (%d non-fatal errors).",
                run_id, len(errors),
            )
        else:
            final_status = RunStatus.completed
            log.info("Run %s: finalising as completed.", run_id)

        await update_run_status(
            run_id,
            final_status,
            runs_db,
            error_message="; ".join(errors[:5]) if errors else None,
            metrics_v1=metrics_v1,
            metrics_v2=metrics_v2,
        )

        return {"final_status": final_status.value}

    return finalize
