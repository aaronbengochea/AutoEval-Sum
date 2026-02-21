"""
LangGraph StateGraph definition for the AutoEval-Sum run pipeline.

Node flow
---------
load_docs → init_run → eval_author_v1 → execute_v1 → judge_v1
          → curriculum_v2 → execute_v2 → judge_v2 → finalize

Conditional routing
-------------------
After each major node, if cancel_requested is True the graph routes directly
to finalize so state is always cleanly written to DynamoDB before exit.

Usage
-----
    graph = build_graph(docs_db=..., runs_db=...)
    result = await graph.ainvoke(initial_state)
"""

import logging
from typing import Any, Literal

from langgraph.graph import END, StateGraph

from autoeval_sum.db.client import DynamoDBClient
from autoeval_sum.runtime.nodes.curriculum import make_curriculum_node
from autoeval_sum.runtime.nodes.eval_author import make_eval_author_node
from autoeval_sum.runtime.nodes.execute import make_execute_node
from autoeval_sum.runtime.nodes.finalize import make_finalize_node
from autoeval_sum.runtime.nodes.init_run import make_init_run_node
from autoeval_sum.runtime.nodes.judge import make_judge_node
from autoeval_sum.runtime.nodes.load_docs import make_load_docs_node
from autoeval_sum.runtime.state import RunState
from autoeval_sum.vector.client import PineconeClient

log = logging.getLogger(__name__)


# ── Routing helpers ────────────────────────────────────────────────────────────

def _route_after(next_node: str, finalize_node: str = "finalize") -> Any:
    """
    Return a routing function that goes to `next_node` normally, or
    jumps straight to `finalize` when cancel is requested.
    """
    def router(state: RunState) -> Literal["finalize"] | str:  # type: ignore[return]
        if state.get("cancel_requested"):
            log.debug("Routing to finalize (cancel_requested=True).")
            return finalize_node
        return next_node

    router.__name__ = f"route_to_{next_node}"
    return router


# ── Graph factory ──────────────────────────────────────────────────────────────

def build_graph(
    docs_db: DynamoDBClient,
    runs_db: DynamoDBClient,
    suites_db: DynamoDBClient | None = None,
    results_db: DynamoDBClient | None = None,
    vector_client: PineconeClient | None = None,
) -> Any:
    """
    Compile and return the run pipeline StateGraph.

    Parameters
    ----------
    docs_db:
        DynamoDB client for the Documents table.
    runs_db:
        DynamoDB client for the AutoEvalRuns table.
    suites_db:
        DynamoDB client for the EvalSuites table (optional; enables suite persistence).
    results_db:
        DynamoDB client for the EvalResults table (optional; enables result persistence).
    vector_client:
        PineconeClient for eval prompt indexing, failure memory, and dedup
        (optional; enables all Pinecone operations).
    """
    graph: StateGraph = StateGraph(RunState)  # type: ignore[type-arg]

    # ── Register nodes ─────────────────────────────────────────────────────────
    graph.add_node("load_docs", make_load_docs_node(docs_db))
    graph.add_node("init_run", make_init_run_node())
    graph.add_node("eval_author_v1", make_eval_author_node("v1", vector_client=vector_client))
    graph.add_node("execute_v1", make_execute_node("v1"))
    graph.add_node(
        "judge_v1",
        make_judge_node("v1", results_db=results_db, vector_client=vector_client),
    )
    graph.add_node(
        "curriculum_v2",
        make_curriculum_node(vector_client=vector_client),
    )
    graph.add_node("execute_v2", make_execute_node("v2"))
    graph.add_node(
        "judge_v2",
        make_judge_node("v2", results_db=results_db, vector_client=vector_client),
    )
    graph.add_node("finalize", make_finalize_node(runs_db, suites_db=suites_db))

    # ── Entry point ────────────────────────────────────────────────────────────
    graph.set_entry_point("load_docs")

    # ── Edges with cancel routing ──────────────────────────────────────────────
    graph.add_edge("load_docs", "init_run")

    # After init_run → eval_author_v1 (or finalize on cancel)
    graph.add_conditional_edges(
        "init_run",
        _route_after("eval_author_v1"),
        {"eval_author_v1": "eval_author_v1", "finalize": "finalize"},
    )
    graph.add_conditional_edges(
        "eval_author_v1",
        _route_after("execute_v1"),
        {"execute_v1": "execute_v1", "finalize": "finalize"},
    )
    graph.add_conditional_edges(
        "execute_v1",
        _route_after("judge_v1"),
        {"judge_v1": "judge_v1", "finalize": "finalize"},
    )
    graph.add_conditional_edges(
        "judge_v1",
        _route_after("curriculum_v2"),
        {"curriculum_v2": "curriculum_v2", "finalize": "finalize"},
    )
    graph.add_conditional_edges(
        "curriculum_v2",
        _route_after("execute_v2"),
        {"execute_v2": "execute_v2", "finalize": "finalize"},
    )
    graph.add_conditional_edges(
        "execute_v2",
        _route_after("judge_v2"),
        {"judge_v2": "judge_v2", "finalize": "finalize"},
    )
    graph.add_edge("judge_v2", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()
