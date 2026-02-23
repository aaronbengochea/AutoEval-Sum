"""
Shared helpers for graph nodes.

Keeps doc conversion, metrics computation, and catalog utilities in one place
so individual node files stay focused on orchestration logic.
"""

import logging
from collections import Counter
from pathlib import Path
from typing import Any

from autoeval_sum.config.settings import get_settings

from autoeval_sum.models.documents import EnrichedDocument
from autoeval_sum.models.schemas import EvalCase, JudgeCaseResult, SuiteMetrics

log = logging.getLogger(__name__)


# ── Document helpers ──────────────────────────────────────────────────────────

def doc_from_dynamo_item(item: dict[str, Any]) -> EnrichedDocument:
    """
    Build an EnrichedDocument from a raw DynamoDB record.

    The `text` field is set to "" because it is only used in execute nodes
    (which read from content_path directly). For catalog-only uses (eval_author,
    curriculum) the empty string is fine.
    """
    return EnrichedDocument(
        doc_id=str(item["doc_id"]),
        text="",
        url=str(item.get("url", "")),
        source_query_id=int(item.get("source_query_id", 0)),
        word_count=int(item["word_count"]),
        token_count=int(item["token_count"]),
        was_truncated=bool(item.get("was_truncated", False)),
        entity_density=float(item["entity_density"]),
        difficulty_tag=item["difficulty_tag"],
        category_tag=str(item["category_tag"]),
        content_path=str(item["content_path"]),
    )


def read_doc_text(content_path: str) -> str:
    """Read document text from its on-disk content file.

    content_path is relative to the data/ root (e.g. "corpus/{doc_id}.txt").
    """
    path = Path(get_settings().data_dir) / content_path
    if not path.exists():
        raise FileNotFoundError(f"Document text not found at {content_path}")
    return path.read_text(encoding="utf-8")


def doc_map_from_items(items: list[dict[str, Any]]) -> dict[str, EnrichedDocument]:
    """Return a doc_id → EnrichedDocument index for fast lookup."""
    return {doc_from_dynamo_item(item).doc_id: doc_from_dynamo_item(item) for item in items}


# ── Metrics helpers ───────────────────────────────────────────────────────────

def compute_suite_metrics(
    suite_id: str,
    eval_suite: list[dict[str, Any]],
    judge_results: list[dict[str, Any]],
    suite_size: int = 20,
) -> SuiteMetrics:
    """
    Derive SuiteMetrics from judge results.

    Parameters
    ----------
    suite_id:
        Format: {run_id}#v{n}
    eval_suite:
        Serialised EvalCase list (used to look up worst examples).
    judge_results:
        Serialised JudgeCaseResult list.
    suite_size:
        Total number of cases in the suite. Used to derive the regression-core
        size (40% of suite_size, minimum 1) passed to the Curriculum agent.
    """
    if not judge_results:
        # No results — return zero metrics
        zero_dims = {
            "coverage": 0.0, "faithfulness": 0.0, "conciseness": 0.0, "structure": 0.0
        }
        return SuiteMetrics(
            suite_id=suite_id,
            avg_scores_by_dimension=zero_dims,
            aggregate_avg=0.0,
            pass_rate=0.0,
            failure_detection_rate=0.0,
            top_failure_modes=[],
            worst_examples=[],
        )

    validated_results = [JudgeCaseResult.model_validate(r) for r in judge_results]
    n = len(validated_results)

    # Dimension averages
    dim_totals: dict[str, float] = {
        "coverage": 0.0,
        "faithfulness": 0.0,
        "conciseness": 0.0,
        "structure": 0.0,
    }
    aggregate_total = 0.0
    pass_count = 0
    fail_count = 0
    failure_tag_counter: Counter[str] = Counter()

    for r in validated_results:
        dim_totals["coverage"] += r.scores.coverage
        dim_totals["faithfulness"] += r.scores.faithfulness
        dim_totals["conciseness"] += r.scores.conciseness
        dim_totals["structure"] += r.scores.structure
        aggregate_total += r.aggregate_score
        if r.pass_result:
            pass_count += 1
        else:
            fail_count += 1
            for tag in r.failure_tags:
                failure_tag_counter[tag] += 1

    avg_scores = {dim: round(total / n, 4) for dim, total in dim_totals.items()}
    aggregate_avg = round(aggregate_total / n, 4)
    pass_rate = round(pass_count / n, 4)
    failure_detection_rate = round(fail_count / n, 4)
    top_failure_modes = [tag for tag, _ in failure_tag_counter.most_common(5)]

    # Worst examples: bottom 40% of suite_size (regression core for curriculum)
    n_worst = max(1, round(suite_size * 0.4))
    result_by_eval_id = {r.eval_id: r for r in validated_results}
    sorted_results = sorted(validated_results, key=lambda r: r.aggregate_score)
    worst_eval_ids = {r.eval_id for r in sorted_results[:n_worst]}
    worst_examples = [
        EvalCase.model_validate(c)
        for c in eval_suite
        if c.get("eval_id") in worst_eval_ids
    ]

    log.info(
        "Suite %s — n=%d  pass_rate=%.2f  aggregate_avg=%.2f  top_failures=%s",
        suite_id, n, pass_rate, aggregate_avg, top_failure_modes[:3],
    )

    _ = result_by_eval_id  # referenced for completeness, not used directly

    return SuiteMetrics(
        suite_id=suite_id,
        avg_scores_by_dimension=avg_scores,
        aggregate_avg=aggregate_avg,
        pass_rate=pass_rate,
        failure_detection_rate=failure_detection_rate,
        top_failure_modes=top_failure_modes,
        worst_examples=worst_examples,
    )
