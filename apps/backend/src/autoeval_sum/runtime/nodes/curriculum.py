"""
curriculum_v2 node — generates the v2 eval suite from v1 results.
"""

import logging
from typing import Any

from autoeval_sum.agents.curriculum import run_curriculum
from autoeval_sum.agents.summarizer import AgentError
from autoeval_sum.models.schemas import EvalCase, SuiteMetrics
from autoeval_sum.runtime.nodes.helpers import doc_from_dynamo_item
from autoeval_sum.runtime.policies import CURRICULUM_FLAT_TOKENS, with_retry
from autoeval_sum.runtime.queue import get_run_queue
from autoeval_sum.runtime.state import RunState

log = logging.getLogger(__name__)


async def curriculum_v2(state: RunState) -> dict:  # type: ignore[type-arg]
    """
    Build the v2 eval suite from v1 metrics and worst examples.

    Pinecone context is empty in Phase 4 (integrated in Phase 5).
    """
    run_id: str = state.get("run_id", "unknown")

    if get_run_queue().check_cancel():
        log.info("Run %s: cancel before curriculum_v2.", run_id)
        return {"cancel_requested": True}

    metrics_v1_data = state.get("metrics_v1")
    if not metrics_v1_data:
        err = "curriculum_v2: metrics_v1 is missing — cannot generate v2 suite"
        log.error(err)
        errors = list(state.get("errors", []))
        errors.append(err)
        return {"errors": errors, "cancel_requested": True}

    metrics_v1 = SuiteMetrics.model_validate(metrics_v1_data)
    worst_examples = [EvalCase.model_validate(c) for c in metrics_v1.worst_examples]

    docs_data: list[dict[str, Any]] = state.get("docs", [])
    enriched_docs = [doc_from_dynamo_item(item) for item in docs_data]
    suite_size: int = state.get("suite_size", 20)
    budget_used: int = state.get("token_budget_used", 0)

    try:
        output = await with_retry(
            run_curriculum,
            metrics_v1,
            worst_examples,
            enriched_docs,
            [],            # pinecone_similar_prompts — Phase 5 integration
            suite_size,
            "v2",
            max_retries=3,
        )
    except AgentError as exc:
        log.error("curriculum_v2 failed: %s", exc)
        errors = list(state.get("errors", []))
        errors.append(f"curriculum_v2: {exc}")
        return {"errors": errors, "cancel_requested": True}

    serialised = [c.model_dump(by_alias=True) for c in output.next_suite]
    new_budget = budget_used + CURRICULUM_FLAT_TOKENS

    log.info(
        "Run %s: curriculum_v2 — %d v2 cases  (retained=%d, new=%d)",
        run_id,
        len(serialised),
        output.improvement_plan.retained_count,
        output.improvement_plan.replaced_count,
    )

    return {
        "eval_suite_v2": serialised,
        "token_budget_used": new_budget,
    }


def make_curriculum_node() -> Any:
    """Return the curriculum_v2 node (no injected dependencies needed)."""
    return curriculum_v2
