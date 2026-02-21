"""
execute node — runs the Summarizer on each eval case in a suite.

Shared by both iterations (v1 and v2) via the make_execute_node factory.
Applies bounded parallelism (4 workers), per-call retry, and token budget checks.
"""

import asyncio
import logging
from typing import Any

from autoeval_sum.agents.summarizer import AgentError, run_summarizer
from autoeval_sum.models.schemas import EvalCase
from autoeval_sum.runtime.nodes.helpers import doc_from_dynamo_item, read_doc_text
from autoeval_sum.runtime.policies import (
    SUMMARIZER_OVERHEAD_TOKENS,
    TokenBudget,
    TokenBudgetExceededError,
    make_semaphore,
    with_retry,
)
from autoeval_sum.runtime.queue import get_run_queue
from autoeval_sum.runtime.state import CaseExecution, RunState

log = logging.getLogger(__name__)


def make_execute_node(suite_version: str = "v1") -> Any:
    """
    Return the execute node for the given suite version.

    The node runs the Summarizer on every eval case in the suite, using:
    - 4-worker asyncio.Semaphore for bounded parallelism
    - 3-retry exponential backoff for each Gemini call
    - TokenBudget checked before each case; soft-stops on cap
    - Cancel check between cases
    """
    from autoeval_sum.config.settings import get_settings

    async def execute(state: RunState) -> dict:  # type: ignore[type-arg]
        settings = get_settings()
        suite_key = f"eval_suite_{suite_version}"
        exec_key = f"executions_{suite_version}"

        suite_data: list[dict[str, Any]] = state.get(suite_key, [])  # type: ignore[assignment]
        docs_data: list[dict[str, Any]] = state.get("docs", [])
        budget_used: int = state.get("token_budget_used", 0)
        existing_errors: list[str] = list(state.get("errors", []))

        # Build a doc_id → doc lookup
        doc_lookup = {
            doc_from_dynamo_item(item).doc_id: doc_from_dynamo_item(item)
            for item in docs_data
        }

        suite = [EvalCase.model_validate(c) for c in suite_data]
        budget = TokenBudget(cap=settings.max_token_budget, initial=budget_used)
        sem = make_semaphore(settings.run_workers)
        executions: list[CaseExecution] = []
        errors = list(existing_errors)
        budget_exceeded = False

        async def run_one(case: EvalCase) -> CaseExecution:
            """Execute a single eval case under the semaphore."""
            async with sem:
                if get_run_queue().check_cancel():
                    return CaseExecution(
                        eval_id=case.eval_id,
                        doc_id=case.doc_id,
                        summary=None,
                        error="Cancelled",
                        tokens_used=0,
                    )

                doc = doc_lookup.get(case.doc_id)
                if doc is None:
                    err = f"Document {case.doc_id} not found for case {case.eval_id}"
                    log.warning(err)
                    return CaseExecution(
                        eval_id=case.eval_id,
                        doc_id=case.doc_id,
                        summary=None,
                        error=err,
                        tokens_used=0,
                    )

                try:
                    doc_text = read_doc_text(doc.content_path)
                except FileNotFoundError as exc:
                    return CaseExecution(
                        eval_id=case.eval_id,
                        doc_id=case.doc_id,
                        summary=None,
                        error=str(exc),
                        tokens_used=0,
                    )

                try:
                    summary = await with_retry(
                        run_summarizer,
                        doc_text,
                        case.constraints or None,
                        max_retries=3,
                    )
                except AgentError as exc:
                    log.warning("Summarizer failed for %s: %s", case.eval_id, exc)
                    return CaseExecution(
                        eval_id=case.eval_id,
                        doc_id=case.doc_id,
                        summary=None,
                        error=str(exc),
                        tokens_used=0,
                    )

                tokens_est = doc.token_count + SUMMARIZER_OVERHEAD_TOKENS
                return CaseExecution(
                    eval_id=case.eval_id,
                    doc_id=case.doc_id,
                    summary=summary.model_dump(),
                    error=None,
                    tokens_used=tokens_est,
                )

        # Process cases sequentially in batches respecting cancel + token cap.
        # asyncio.gather is used within each batch so the semaphore provides the
        # actual parallelism control.
        tasks = [asyncio.create_task(run_one(c)) for c in suite]
        for task in asyncio.as_completed(tasks):
            result: CaseExecution = await task
            executions.append(result)

            if result["error"]:
                errors.append(f"{result['eval_id']}: {result['error']}")

            try:
                budget.add(result["tokens_used"])
            except TokenBudgetExceededError as exc:
                log.warning("Token budget exceeded during %s: %s", suite_version, exc)
                errors.append(f"token_cap_exceeded: {exc}")
                budget_exceeded = True
                # Cancel outstanding tasks and break
                for t in tasks:
                    t.cancel()
                break

            if get_run_queue().check_cancel():
                for t in tasks:
                    t.cancel()
                break

        # Collect any remaining completed tasks before returning
        for task in tasks:
            if not task.done():
                task.cancel()
            if task.done() and not task.cancelled():
                try:
                    remaining = task.result()
                    if not any(e["eval_id"] == remaining["eval_id"] for e in executions):
                        executions.append(remaining)
                except Exception:
                    pass

        log.info(
            "Run %s: execute_%s — %d/%d cases completed  budget_used=%d",
            state.get("run_id"),
            suite_version,
            sum(1 for e in executions if e["error"] is None),
            len(suite),
            budget.used,
        )

        updates: dict[str, Any] = {
            exec_key: executions,
            "token_budget_used": budget.used,
            "errors": errors,
        }
        if budget_exceeded:
            updates["cancel_requested"] = True

        return updates

    execute.__name__ = f"execute_{suite_version}"
    return execute
