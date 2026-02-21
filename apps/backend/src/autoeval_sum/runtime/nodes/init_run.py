"""
init_run node — initialises mutable run-state fields before execution begins.
"""

import logging
from typing import Any

from autoeval_sum.runtime.state import RunState

log = logging.getLogger(__name__)


async def init_run(state: RunState) -> dict:  # type: ignore[type-arg]
    """Reset all mutable counters and lists at the start of a run."""
    log.info("Run %s: initialising state.", state.get("run_id"))
    return {
        "token_budget_used": 0,
        "cancel_requested": False,
        "errors": [],
        "eval_suite_v1": [],
        "executions_v1": [],
        "judge_results_v1": [],
        "metrics_v1": None,
        "eval_suite_v2": [],
        "executions_v2": [],
        "judge_results_v2": [],
        "metrics_v2": None,
    }


def make_init_run_node() -> Any:
    """Return the init_run node (no injected dependencies needed)."""
    return init_run
