"""
Judge Agent.

Scores a single summary against its source document.
Enforces hallucination auto-fail and validates all output constraints.
Calls Gemini at temperature 0 with JSON mode.
"""

import asyncio
import json
import logging

from google import generativeai as genai
from google.generativeai import GenerativeModel

from autoeval_sum.agents.prompts.judge import JUDGE_SYSTEM_PROMPT, JUDGE_USER_TEMPLATE
from autoeval_sum.agents.prompts.rubric import FAILURE_TAXONOMY, RUBRIC_TEXT
from autoeval_sum.agents.summarizer import AgentError
from autoeval_sum.config.settings import get_settings
from autoeval_sum.models.schemas import (
    EvalCase,
    JudgeCaseResult,
    ScoreCard,
    SummaryStructured,
)

log = logging.getLogger(__name__)

_model: GenerativeModel | None = None


def _get_model() -> GenerativeModel:
    global _model
    if _model is None:
        settings = get_settings()
        genai.configure(api_key=settings.google_api_key)
        _model = GenerativeModel(settings.llm_model)
    return _model


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


async def run_judge(
    eval_case: EvalCase,
    doc_text: str,
    summary: SummaryStructured,
) -> JudgeCaseResult:
    """
    Evaluate a single summary and return a validated JudgeCaseResult.

    Parameters
    ----------
    eval_case:
        The eval case being judged (provides eval_id and rubric_note).
    doc_text:
        The source document text (truncated to <=2 048 tokens).
    summary:
        The structured summary produced by the Summarizer Agent.

    Returns
    -------
    JudgeCaseResult
        Fully validated result with corrected pass flag (hallucination overrides).

    Raises
    ------
    AgentError
        On Gemini call failure, JSON parse error, or schema violation.
    """
    system_prompt = JUDGE_SYSTEM_PROMPT.format(
        rubric_text=RUBRIC_TEXT,
        failure_taxonomy=FAILURE_TAXONOMY,
        eval_id=eval_case.eval_id,
    )
    user_message = JUDGE_USER_TEMPLATE.format(
        rubric_note=eval_case.rubric_note or "Evaluate according to the standard rubric.",
        doc_text=doc_text,
        summary_json=summary.model_dump_json(indent=2),
    )

    full_prompt = f"{system_prompt}\n\n{user_message}"

    loop = asyncio.get_event_loop()
    try:
        raw = await loop.run_in_executor(None, _call_gemini, full_prompt)
    except Exception as exc:
        raise AgentError("judge", f"Gemini call failed: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AgentError("judge", f"Response is not valid JSON: {exc}", raw) from exc

    # Ensure eval_id matches the case
    data["eval_id"] = eval_case.eval_id

    # Compute aggregate from scores if present, overriding any LLM-computed value
    if "scores" in data:
        try:
            scores = ScoreCard.model_validate(data["scores"])
            data["aggregate_score"] = round(scores.aggregate, 4)
            # Recompute pass using canonical rule
            hallucination = bool(data.get("hallucination_flag", False))
            data["pass"] = JudgeCaseResult.compute_pass(data["aggregate_score"], hallucination)
        except Exception:
            pass  # Let Pydantic validation surface the error below

    try:
        result = JudgeCaseResult.model_validate(data)
    except Exception as exc:
        raise AgentError("judge", f"Schema validation failed: {exc}", raw) from exc

    log.debug(
        "Judge %s — aggregate=%.2f  pass=%s  hallucination=%s  tags=%s",
        result.eval_id,
        result.aggregate_score,
        result.pass_result,
        result.hallucination_flag,
        result.failure_tags,
    )
    return result
