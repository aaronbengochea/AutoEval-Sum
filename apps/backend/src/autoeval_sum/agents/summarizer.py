"""
Summarizer Agent.

Calls Gemini at temperature 0 with JSON mode enabled to produce a
SummaryStructured output.  On any parse or validation failure the agent
raises AgentError with a structured message — it never silently returns
partial data.
"""

import asyncio
import json
import logging
from typing import Any

from google import generativeai as genai
from google.generativeai import GenerativeModel

from autoeval_sum.agents.prompts.summarizer import (
    SUMMARIZER_SYSTEM_PROMPT,
    SUMMARIZER_USER_TEMPLATE,
)
from autoeval_sum.config.settings import get_settings
from autoeval_sum.models.schemas import SummaryStructured

log = logging.getLogger(__name__)

_model: GenerativeModel | None = None


class AgentError(Exception):
    """Raised when an agent cannot produce a valid structured output."""

    def __init__(self, agent_name: str, reason: str, raw_output: str = "") -> None:
        self.agent_name = agent_name
        self.reason = reason
        self.raw_output = raw_output
        super().__init__(f"[{agent_name}] {reason}")


def _get_model() -> GenerativeModel:
    global _model
    if _model is None:
        settings = get_settings()
        genai.configure(api_key=settings.google_api_key)
        _model = GenerativeModel(settings.llm_model)
    return _model


def _format_constraints(constraints: dict[str, Any] | list[str] | None) -> str:
    if not constraints:
        return "None"
    if isinstance(constraints, list):
        return "\n".join(f"- {c}" for c in constraints)
    return "\n".join(f"- {k}: {v}" for k, v in constraints.items())


def _call_gemini(system_prompt: str, user_message: str) -> str:
    """Synchronous Gemini call with JSON mode. Runs in executor for async use."""
    model = _get_model()
    full_prompt = f"{system_prompt}\n\n{user_message}"
    response = model.generate_content(
        full_prompt,
        generation_config=genai.GenerationConfig(
            temperature=0,
            response_mime_type="application/json",
        ),
    )
    return response.text.strip()


async def run_summarizer(
    doc_text: str,
    constraints: dict[str, Any] | list[str] | None = None,
) -> SummaryStructured:
    """
    Summarize a document and return a validated SummaryStructured.

    Parameters
    ----------
    doc_text:
        The source document text (should already be truncated to <=2 048 tokens).
    constraints:
        Optional additional instructions for this specific eval case.

    Returns
    -------
    SummaryStructured
        Validated structured summary.

    Raises
    ------
    AgentError
        If Gemini returns unparseable JSON or the output fails Pydantic validation.
    """
    user_message = SUMMARIZER_USER_TEMPLATE.format(
        doc_text=doc_text,
        constraints=_format_constraints(constraints),
    )

    loop = asyncio.get_event_loop()
    try:
        raw = await loop.run_in_executor(
            None, _call_gemini, SUMMARIZER_SYSTEM_PROMPT, user_message
        )
    except Exception as exc:
        raise AgentError("summarizer", f"Gemini call failed: {exc}") from exc

    # Parse JSON
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AgentError(
            "summarizer",
            f"Response is not valid JSON: {exc}",
            raw_output=raw,
        ) from exc

    # Validate schema (catches word-count violations, missing fields, etc.)
    try:
        result = SummaryStructured.model_validate(data)
    except Exception as exc:
        raise AgentError(
            "summarizer",
            f"Schema validation failed: {exc}",
            raw_output=raw,
        ) from exc

    log.debug(
        "Summarizer OK — title=%r, abstract_words=%d",
        result.title,
        len(result.abstract.split()),
    )
    return result
