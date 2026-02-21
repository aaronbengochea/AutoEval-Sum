"""
Eval Author Agent.

Produces a list of EvalCase objects that form an evaluation suite.
Calls Gemini at temperature 0 with JSON mode.
"""

import asyncio
import json
import logging

from google import generativeai as genai
from google.generativeai import GenerativeModel

from autoeval_sum.agents.prompts.eval_author import EVAL_AUTHOR_SYSTEM_PROMPT
from autoeval_sum.agents.prompts.rubric import FAILURE_TAXONOMY
from autoeval_sum.agents.summarizer import AgentError
from autoeval_sum.config.settings import get_settings
from autoeval_sum.models.documents import EnrichedDocument
from autoeval_sum.models.schemas import EvalCase

log = logging.getLogger(__name__)

_model: GenerativeModel | None = None

AGENT_SPEC = (
    "A Gemini-based summarization agent that produces a structured summary with a title, "
    "five key points (each ≤ 24 words), and an abstract (≤ 120 words). "
    "The agent operates at temperature 0 and receives documents truncated to 2 048 tokens."
)

DIFFICULTY_MIX = "30% easy, 40% medium, 30% hard"


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


def _unique_categories(docs: list[EnrichedDocument]) -> str:
    return ", ".join(sorted({d.category_tag for d in docs}))


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


async def run_eval_author(
    docs: list[EnrichedDocument],
    suite_size: int,
    suite_version: str = "v1",
) -> list[EvalCase]:
    """
    Generate an evaluation suite for the given document catalog.

    Parameters
    ----------
    docs:
        The enriched corpus to draw eval cases from.
    suite_size:
        Number of eval cases to generate.
    suite_version:
        Version tag used in eval_id format (e.g. "v1").

    Returns
    -------
    list[EvalCase]
        Validated eval cases.  Raises AgentError on any failure.
    """
    doc_catalog = _build_doc_catalog(docs)
    category_targets = _unique_categories(docs)

    # Replace v1 in the prompt with the actual version tag
    system_prompt = EVAL_AUTHOR_SYSTEM_PROMPT.replace("v1-case-", f"{suite_version}-case-")

    prompt = system_prompt.format(
        agent_spec=AGENT_SPEC,
        doc_catalog=doc_catalog,
        suite_size=suite_size,
        difficulty_mix=DIFFICULTY_MIX,
        category_targets=category_targets,
        failure_taxonomy=FAILURE_TAXONOMY,
    )

    loop = asyncio.get_event_loop()
    try:
        raw = await loop.run_in_executor(None, _call_gemini, prompt)
    except Exception as exc:
        raise AgentError("eval_author", f"Gemini call failed: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AgentError("eval_author", f"Response is not valid JSON: {exc}", raw) from exc

    if not isinstance(data, list):
        raise AgentError("eval_author", f"Expected JSON array, got {type(data).__name__}", raw)

    try:
        cases = [EvalCase.model_validate(item) for item in data]
    except Exception as exc:
        raise AgentError("eval_author", f"Schema validation failed: {exc}", raw) from exc

    if len(cases) != suite_size:
        log.warning(
            "Eval author returned %d cases but suite_size=%d; proceeding with %d",
            len(cases), suite_size, len(cases),
        )

    log.info("Eval author produced %d cases for suite %s", len(cases), suite_version)
    return cases
