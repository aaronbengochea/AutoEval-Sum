"""
judge node — scores summaries produced by the execute node.

Shared by both iterations (v1 and v2) via the make_judge_node factory.
Computes per-case JudgeCaseResult, suite-level SuiteMetrics, persists
both to DynamoDB, and (for v1) stores failures in Pinecone and loads
failure exemplars for the curriculum agent.
"""

import asyncio
import logging
from typing import Any

from autoeval_sum.agents.judge import run_judge
from autoeval_sum.agents.summarizer import AgentError
from autoeval_sum.db.client import DynamoDBClient
from autoeval_sum.db.results import save_results_batch
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
from autoeval_sum.vector.client import PineconeClient
from autoeval_sum.vector.memory import retrieve_failure_exemplars, store_failures

log = logging.getLogger(__name__)


def make_judge_node(
    suite_version: str = "v1",
    results_db: DynamoDBClient | None = None,
    vector_client: PineconeClient | None = None,
) -> Any:
    """
    Return the judge node for the given suite version.

    Iterates over all successful executions, runs the Judge agent with retry,
    computes SuiteMetrics, and persists individual results to EvalResults.
    For v1, also stores failures in Pinecone and retrieves failure exemplars
    for the curriculum agent.

    Parameters
    ----------
    suite_version:
        "v1" or "v2".
    results_db:
        DynamoDB client for the EvalResults table. If None, persistence is skipped.
    vector_client:
        PineconeClient for failure memory. If None, Pinecone steps are skipped.
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

        # Persist results to DynamoDB
        if results_db is not None and judge_results:
            try:
                await save_results_batch(suite_id, judge_results, results_db)
            except Exception as exc:
                log.error("Failed to persist results for %s: %s", suite_id, exc)
                errors.append(f"persist_results_{suite_version}: {exc}")

        # Pinecone failure memory (v1 only — v2 failures go to storage but not used further)
        failure_exemplars: list[str] = []
        if vector_client is not None:
            try:
                await store_failures(
                    judge_results, suite_data, run_id, suite_version, vector_client
                )
            except Exception as exc:
                log.error("Failed to store failures in Pinecone: %s", exc)

            if suite_version == "v1" and metrics.top_failure_modes:
                try:
                    failure_exemplars = await retrieve_failure_exemplars(
                        metrics.top_failure_modes, vector_client
                    )
                except Exception as exc:
                    log.warning("Failed to retrieve failure exemplars: %s", exc)

        log.info(
            "Run %s: judge_%s — %d results  pass_rate=%.2f  aggregate=%.2f",
            run_id, suite_version,
            len(judge_results),
            metrics.pass_rate,
            metrics.aggregate_avg,
        )

        updates: dict[str, Any] = {
            results_key: judge_results,
            metrics_key: metrics.model_dump(),
            "token_budget_used": budget.used,
            "errors": errors,
        }
        if failure_exemplars:
            updates["pinecone_failure_exemplars"] = failure_exemplars
        return updates

    judge.__name__ = f"judge_{suite_version}"
    return judge
