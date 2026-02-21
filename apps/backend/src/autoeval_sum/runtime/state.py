"""
LangGraph RunState TypedDict.

All graph nodes receive and return an instance of RunState.  LangGraph
merges the returned dict into the current state automatically.
"""

from typing import Any, TypedDict


class CaseExecution(TypedDict):
    """Result of running the Summarizer for one eval case."""

    eval_id: str
    doc_id: str
    summary: dict[str, Any] | None  # serialised SummaryStructured
    error: str | None
    tokens_used: int


class RunState(TypedDict, total=False):
    """
    Shared state that flows through every node in the graph.

    Fields are optional (total=False) so nodes can return only the keys
    they modify; LangGraph merges the partial update into the full state.

    Required fields (set during init_run / load_docs)
    --------------------------------------------------
    run_id          UUIDv7 string
    seed            RNG seed
    corpus_size     Total documents to load
    suite_size      Eval cases per suite iteration

    Flow fields (written progressively by each node)
    -------------------------------------------------
    docs            Enriched document items from DynamoDB
    eval_suite_v1   EvalCase list for iteration 1
    executions_v1   Summarizer results for iteration 1
    judge_results_v1  JudgeCaseResult list for iteration 1
    metrics_v1      SuiteMetrics dict for iteration 1
    eval_suite_v2   EvalCase list for iteration 2
    executions_v2   Summarizer results for iteration 2
    judge_results_v2  JudgeCaseResult list for iteration 2
    metrics_v2      SuiteMetrics dict for iteration 2

    Control fields
    --------------
    token_budget_used   Running token count across all agent calls
    cancel_requested    Set to True by the queue cancel signal
    errors              Non-fatal case-level error messages
    final_status        Written by the finalize node
    """

    # Identity
    run_id: str
    seed: int
    corpus_size: int
    suite_size: int

    # Loaded corpus
    docs: list[dict[str, Any]]

    # Iteration 1
    eval_suite_v1: list[dict[str, Any]]    # serialised EvalCase list
    executions_v1: list[CaseExecution]
    judge_results_v1: list[dict[str, Any]]  # serialised JudgeCaseResult list
    metrics_v1: dict[str, Any] | None

    # Iteration 2
    eval_suite_v2: list[dict[str, Any]]
    executions_v2: list[CaseExecution]
    judge_results_v2: list[dict[str, Any]]
    metrics_v2: dict[str, Any] | None

    # Pinecone context (populated by judge_v1 for use in curriculum_v2)
    pinecone_failure_exemplars: list[str]

    # Control
    token_budget_used: int
    cancel_requested: bool
    errors: list[str]
    final_status: str  # RunStatus.value
