"""
finalize node — persists the final run status and suite metrics to DynamoDB.
"""

import logging
from typing import Any

from autoeval_sum.db.client import DynamoDBClient
from autoeval_sum.db.runs import update_run_status
from autoeval_sum.db.suites import save_suite
from autoeval_sum.models.runs import RunStatus
from autoeval_sum.runtime.queue import get_run_queue
from autoeval_sum.runtime.state import RunState

log = logging.getLogger(__name__)


def make_finalize_node(
    runs_db: DynamoDBClient,
    suites_db: DynamoDBClient | None = None,
) -> Any:
    """
    Return the finalize node with injected DynamoDB clients.

    Parameters
    ----------
    runs_db:
        DynamoDB client for AutoEvalRuns table.
    suites_db:
        DynamoDB client for EvalSuites table. If None, suite persistence is skipped.
    """

    async def finalize(state: RunState) -> dict:  # type: ignore[type-arg]
        run_id: str = state.get("run_id", "unknown")
        errors: list[str] = state.get("errors", [])
        metrics_v1: dict[str, Any] | None = state.get("metrics_v1")
        metrics_v2: dict[str, Any] | None = state.get("metrics_v2")

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

        # Persist run terminal state
        await update_run_status(
            run_id,
            final_status,
            runs_db,
            error_message="; ".join(errors[:5]) if errors else None,
            metrics_v1=metrics_v1,
            metrics_v2=metrics_v2,
        )

        # Persist suite-level metrics to EvalSuites
        if suites_db is not None:
            if metrics_v1:
                try:
                    await save_suite(run_id, "v1", metrics_v1, suites_db)
                except Exception as exc:
                    log.error("Failed to persist suite v1 for run %s: %s", run_id, exc)
            if metrics_v2:
                try:
                    await save_suite(run_id, "v2", metrics_v2, suites_db)
                except Exception as exc:
                    log.error("Failed to persist suite v2 for run %s: %s", run_id, exc)

        return {"final_status": final_status.value}

    return finalize
