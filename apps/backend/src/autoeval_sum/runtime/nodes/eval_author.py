"""
eval_author node — generates an evaluation suite (v1 only; v2 comes from curriculum).

After generating the suite, upserts each eval case prompt to the Pinecone
eval_prompts namespace so future dedup checks can compare against it.
"""

import logging
from typing import Any

from autoeval_sum.agents.eval_author import run_eval_author
from autoeval_sum.agents.summarizer import AgentError
from autoeval_sum.runtime.nodes.helpers import doc_from_dynamo_item
from autoeval_sum.runtime.policies import (
    EVAL_AUTHOR_FLAT_TOKENS,
    TokenBudgetExceededError,
    with_retry,
)
from autoeval_sum.runtime.queue import get_run_queue
from autoeval_sum.runtime.state import RunState
from autoeval_sum.vector.client import PineconeClient
from autoeval_sum.vector.memory import upsert_eval_prompts

log = logging.getLogger(__name__)


def make_eval_author_node(
    suite_version: str = "v1",
    vector_client: PineconeClient | None = None,
) -> Any:
    """
    Return the eval_author node for the given suite version.

    Parameters
    ----------
    suite_version:
        "v1" (only v1 is authored here; v2 comes from curriculum).
    vector_client:
        PineconeClient for upserting prompts. If None, Pinecone step is skipped.
    """

    async def eval_author(state: RunState) -> dict:  # type: ignore[type-arg]
        run_id: str = state.get("run_id", "unknown")

        if get_run_queue().check_cancel():
            log.info("Run %s: cancel before eval_author_%s.", run_id, suite_version)
            return {"cancel_requested": True}

        docs = state.get("docs", [])
        suite_size = state.get("suite_size", 20)
        budget_used = state.get("token_budget_used", 0)

        enriched_docs = [doc_from_dynamo_item(item) for item in docs]

        try:
            cases = await with_retry(
                run_eval_author,
                enriched_docs,
                suite_size,
                suite_version,
                max_retries=3,
            )
        except (AgentError, TokenBudgetExceededError) as exc:
            log.error("eval_author_%s failed: %s", suite_version, exc)
            errors = list(state.get("errors", []))
            errors.append(f"eval_author_{suite_version}: {exc}")
            return {"errors": errors, "cancel_requested": True}

        serialised = [c.model_dump(by_alias=True) for c in cases]
        new_budget = budget_used + EVAL_AUTHOR_FLAT_TOKENS

        # Upsert prompts to Pinecone for future dedup checks
        if vector_client is not None:
            await upsert_eval_prompts(serialised, run_id, suite_version, vector_client)

        key = f"eval_suite_{suite_version}"
        log.info(
            "Run %s: eval_author_%s produced %d cases.",
            run_id, suite_version, len(cases),
        )
        return {key: serialised, "token_budget_used": new_budget}

    eval_author.__name__ = f"eval_author_{suite_version}"
    return eval_author
