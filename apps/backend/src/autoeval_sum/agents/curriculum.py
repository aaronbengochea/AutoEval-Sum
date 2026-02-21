"""
Curriculum Agent.

Generates the v2 evaluation suite from v1 results.
Enforces the 40% regression core / 60% new split and the 30/40/30
difficulty mix.  Uses Pinecone context for dedup awareness.
Calls Gemini at temperature 0 with JSON mode.
"""

import asyncio
import json
import logging

from google import generativeai as genai
from google.generativeai import GenerativeModel

from autoeval_sum.agents.prompts.curriculum import CURRICULUM_SYSTEM_PROMPT
from autoeval_sum.agents.prompts.rubric import FAILURE_TAXONOMY
from autoeval_sum.agents.summarizer import AgentError
from autoeval_sum.config.settings import get_settings
from autoeval_sum.models.documents import EnrichedDocument
from autoeval_sum.models.schemas import CurriculumOutput, EvalCase, SuiteMetrics

log = logging.getLogger(__name__)

_model: GenerativeModel | None = None


def _get_model() -> GenerativeModel:
    global _model
    if _model is None:
        settings = get_settings()
        genai.configure(api_key=settings.google_api_key)
        _model = GenerativeModel(settings.llm_model)
    return _model


def _build_doc_catalog(docs: list[EnrichedDocument]) -> str:
    rows = [
        f'{{"doc_id": "{d.doc_id}", "difficulty_tag": "{d.difficulty_tag}", '
        f'"category_tag": "{d.category_tag}", "word_count": {d.word_count}}}'
        for d in docs
    ]
    return "[\n" + ",\n".join(rows) + "\n]"


def _format_pinecone_context(similar_prompts: list[str]) -> str:
    if not similar_prompts:
        return "None retrieved."
    return "\n".join(f"- {p}" for p in similar_prompts)


def _call_gemini(prompt: str) -> str:
    model = _get_model()
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            temperature=0,
            response_mime_type="application/json",
        ),
    )
    return response.text.strip()


async def run_curriculum(
    suite_v1_metrics: SuiteMetrics,
    worst_examples: list[EvalCase],
    docs: list[EnrichedDocument],
    pinecone_similar_prompts: list[str],
    suite_size: int,
    next_suite_version: str = "v2",
) -> CurriculumOutput:
    """
    Generate the next evaluation suite based on v1 results.

    Parameters
    ----------
    suite_v1_metrics:
        Aggregated metrics for the completed v1 suite.
    worst_examples:
        Up to 5 lowest-scoring EvalCase objects from v1.
    docs:
        Full enriched document corpus.
    pinecone_similar_prompts:
        Descriptions of near-duplicate prompts already in Pinecone
        (used to guide the LLM away from semantic duplicates).
    suite_size:
        Target number of eval cases for v2.
    next_suite_version:
        Version tag for the new suite (default "v2").

    Returns
    -------
    CurriculumOutput
        Validated v2 suite with improvement plan.

    Raises
    ------
    AgentError
        On Gemini call failure, JSON parse error, or schema violation.
    """
    top_failure_modes = ", ".join(suite_v1_metrics.top_failure_modes)
    worst_examples_json = json.dumps(
        [c.model_dump(by_alias=True) for c in worst_examples], indent=2
    )
    doc_catalog_json = _build_doc_catalog(docs)
    pinecone_context = _format_pinecone_context(pinecone_similar_prompts)

    prompt = CURRICULUM_SYSTEM_PROMPT.format(
        suite_v1_metrics_json=suite_v1_metrics.model_dump_json(indent=2),
        worst_examples_json=worst_examples_json,
        top_failure_modes=top_failure_modes,
        doc_catalog_json=doc_catalog_json,
        pinecone_context=pinecone_context,
        suite_size=suite_size,
        failure_taxonomy=FAILURE_TAXONOMY,
        next_suite_version=next_suite_version,
    )

    loop = asyncio.get_event_loop()
    try:
        raw = await loop.run_in_executor(None, _call_gemini, prompt)
    except Exception as exc:
        raise AgentError("curriculum", f"Gemini call failed: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AgentError("curriculum", f"Response is not valid JSON: {exc}", raw) from exc

    try:
        result = CurriculumOutput.model_validate(data)
    except Exception as exc:
        raise AgentError("curriculum", f"Schema validation failed: {exc}", raw) from exc

    plan = result.improvement_plan
    log.info(
        "Curriculum v%s — %d cases total  (retained=%d, new=%d, dedup_rejections=%d)",
        next_suite_version,
        len(result.next_suite),
        plan.retained_count,
        plan.replaced_count,
        plan.dedup_rejections,
    )
    return result
