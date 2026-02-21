"""
curriculum_v2 node — generates the v2 eval suite from v1 results.

Integrates Pinecone for:
1. Providing failure exemplar context to the LLM (soft guidance).
2. Post-generation dedup filtering (hard cosine >= 0.90 rejection).
3. Upserting accepted v2 prompts to eval_prompts namespace.
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
from autoeval_sum.vector.client import PineconeClient
from autoeval_sum.vector.dedup import filter_duplicates
from autoeval_sum.vector.memory import upsert_eval_prompts

log = logging.getLogger(__name__)


def make_curriculum_node(vector_client: PineconeClient | None = None) -> Any:
    """
    Return the curriculum_v2 node.

    Parameters
    ----------
    vector_client:
        PineconeClient for dedup + prompt upsert. If None, Pinecone steps are skipped.
    """

    async def curriculum_v2(state: RunState) -> dict:  # type: ignore[type-arg]
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
        errors = list(state.get("errors", []))

        # Use Pinecone failure exemplars as soft guidance for the LLM
        pinecone_similar_prompts: list[str] = state.get("pinecone_failure_exemplars", [])

        try:
            output = await with_retry(
                run_curriculum,
                metrics_v1,
                worst_examples,
                enriched_docs,
                pinecone_similar_prompts,
                suite_size,
                "v2",
                max_retries=3,
            )
        except AgentError as exc:
            log.error("curriculum_v2 failed: %s", exc)
            errors.append(f"curriculum_v2: {exc}")
            return {"errors": errors, "cancel_requested": True}

        candidate_cases = [c.model_dump(by_alias=True) for c in output.next_suite]
        new_budget = budget_used + CURRICULUM_FLAT_TOKENS

        # Hard dedup filter: reject cases with cosine >= 0.90 against eval_prompts
        dedup_rejections = 0
        if vector_client is not None:
            candidate_cases, dedup_rejections = await filter_duplicates(
                candidate_cases, vector_client
            )
            if dedup_rejections:
                log.info(
                    "Run %s: curriculum_v2 dedup removed %d case(s).",
                    run_id, dedup_rejections,
                )

        # Upsert accepted v2 prompts to eval_prompts namespace
        if vector_client is not None and candidate_cases:
            await upsert_eval_prompts(candidate_cases, run_id, "v2", vector_client)

        log.info(
            "Run %s: curriculum_v2 — %d v2 cases  (retained=%d, new=%d, dedup_rejected=%d)",
            run_id,
            len(candidate_cases),
            output.improvement_plan.retained_count,
            output.improvement_plan.replaced_count,
            dedup_rejections,
        )

        return {
            "eval_suite_v2": candidate_cases,
            "token_budget_used": new_budget,
            "errors": errors,
        }

    return curriculum_v2
