"""
judge node — scores summaries produced by the execute node.

Shared by both iterations (v1 and v2) via the make_judge_node factory.
Computes per-case JudgeCaseResult and suite-level SuiteMetrics.
"""

import asyncio
import logging
from typing import Any

from autoeval_sum.agents.judge import run_judge
from autoeval_sum.agents.summarizer import AgentError
from autoeval_sum.models.schemas import EvalCase, SummaryStructured
from autoeval_sum.runtime.nodes.helpers import (
    compute_suite_metrics,
    doc_from_dynamo_item,
    read_doc_text,
)
from autoeval_sum.runtime.policies import (
    JUDGE_OVERHEAD_TOKENS,
    TokenBudget,
    TokenBudgetExceededError,
    make_semaphore,
    with_retry,
)
from autoeval_sum.runtime.queue import get_run_queue
from autoeval_sum.runtime.state import RunState

log = logging.getLogger(__name__)


def make_judge_node(suite_version: str = "v1") -> Any:
    """
    Return the judge node for the given suite version.

    Iterates over all successful executions, runs the Judge agent with retry,
    then computes SuiteMetrics from all results.
    """
    from autoeval_sum.config.settings import get_settings

    iteration_n = suite_version.lstrip("v")

    async def judge(state: RunState) -> dict:  # type: ignore[type-arg]
        settings = get_settings()
        exec_key = f"executions_{suite_version}"
        suite_key = f"eval_suite_{suite_version}"
        results_key = f"judge_results_{suite_version}"
        metrics_key = f"metrics_{suite_version}"

        executions = state.get(exec_key, [])
        suite_data: list[dict[str, Any]] = state.get(suite_key, [])  # type: ignore[assignment]
        docs_data: list[dict[str, Any]] = state.get("docs", [])
        run_id: str = state.get("run_id", "unknown")
        budget_used: int = state.get("token_budget_used", 0)
        existing_errors: list[str] = list(state.get("errors", []))

        # Quick-exit on cancel
        if get_run_queue().check_cancel():
            log.info("Run %s: cancel before judge_%s.", run_id, suite_version)
            return {"cancel_requested": True}

        doc_lookup = {
            doc_from_dynamo_item(item).doc_id: doc_from_dynamo_item(item)
            for item in docs_data
        }
        suite_by_id = {c["eval_id"]: EvalCase.model_validate(c) for c in suite_data}

        budget = TokenBudget(cap=settings.max_token_budget, initial=budget_used)
        sem = make_semaphore(settings.run_workers)
        judge_results: list[dict[str, Any]] = []
        errors = list(existing_errors)

        async def judge_one(exec_item: dict[str, Any]) -> dict[str, Any] | None:
            """Score one execution result; returns None on skip/error."""
            eval_id: str = exec_item["eval_id"]
            doc_id: str = exec_item["doc_id"]
            raw_summary = exec_item.get("summary")

            if raw_summary is None:
                # Summarizer failed — no summary to judge
                return None

            async with sem:
                if get_run_queue().check_cancel():
                    return None

                eval_case = suite_by_id.get(eval_id)
                if eval_case is None:
                    log.warning("EvalCase %s not found; skipping judge.", eval_id)
                    return None

                doc = doc_lookup.get(doc_id)
                if doc is None:
                    log.warning("Doc %s not found for judge of %s.", doc_id, eval_id)
                    return None

                try:
                    doc_text = read_doc_text(doc.content_path)
                except FileNotFoundError as exc:
                    errors.append(f"judge_{suite_version}/{eval_id}: {exc}")
                    return None

                try:
                    summary = SummaryStructured.model_validate(raw_summary)
                except Exception as exc:
                    errors.append(f"judge_{suite_version}/{eval_id}: bad summary schema: {exc}")
                    return None

                try:
                    result = await with_retry(
                        run_judge,
                        eval_case,
                        doc_text,
                        summary,
                        max_retries=3,
                    )
                except AgentError as exc:
                    log.warning("Judge failed for %s: %s", eval_id, exc)
                    errors.append(f"judge_{suite_version}/{eval_id}: {exc}")
                    return None

                tokens_est = doc.token_count + JUDGE_OVERHEAD_TOKENS
                try:
                    budget.add(tokens_est)
                except TokenBudgetExceededError as exc:
                    errors.append(f"token_cap_exceeded during judge_{suite_version}: {exc}")
                    return None

                return result.model_dump(by_alias=True)

        tasks = [asyncio.create_task(judge_one(e)) for e in executions]
        for done_task in asyncio.as_completed(tasks):
            result_dict = await done_task
            if result_dict is not None:
                judge_results.append(result_dict)

        suite_id = f"{run_id}#v{iteration_n}"
        metrics = compute_suite_metrics(suite_id, suite_data, judge_results)

        log.info(
            "Run %s: judge_%s — %d results  pass_rate=%.2f  aggregate=%.2f",
            run_id, suite_version,
            len(judge_results),
            metrics.pass_rate,
            metrics.aggregate_avg,
        )

        return {
            results_key: judge_results,
            metrics_key: metrics.model_dump(),
            "token_budget_used": budget.used,
            "errors": errors,
        }

    judge.__name__ = f"judge_{suite_version}"
    return judge
