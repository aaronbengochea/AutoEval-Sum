"""
Global evaluation rubric definition.

This is the single source of truth for rubric anchors used by the Judge Agent.
All score values are integers 0–5; equal weights across all four dimensions.
Pass threshold: aggregate >= 3.5 AND hallucination_flag is False.
"""

from autoeval_sum.models.schemas import RubricAnchors, RubricGlobal

GLOBAL_RUBRIC = RubricGlobal(
    coverage=RubricAnchors(
        score_0="The summary omits nearly all key points from the source document.",
        score_3="The summary covers the main topic but misses one or two important supporting points.",
        score_5="The summary accurately captures all key points from the source with appropriate emphasis.",
    ),
    faithfulness=RubricAnchors(
        score_0="The summary contains multiple claims that directly contradict or are absent from the source.",
        score_3="The summary is mostly faithful but contains one minor unsupported inference or paraphrase.",
        score_5="Every claim in the summary is directly supported by the source document.",
    ),
    conciseness=RubricAnchors(
        score_0="The summary is severely over-compressed (loses critical meaning) or excessively verbose (redundant filler).",
        score_3="The summary is mostly concise but includes minor redundancy or is slightly over-compressed.",
        score_5="The summary is appropriately dense: no filler, no unnecessary repetition, no critical omissions.",
    ),
    structure=RubricAnchors(
        score_0="The summary has no logical flow; ideas are jumbled or the format is broken.",
        score_3="The summary has a recognisable structure but transitions are awkward or ordering is suboptimal.",
        score_5="The summary is well-organised with clear logical flow and appropriate use of the structured format.",
    ),
)

RUBRIC_TEXT = """
EVALUATION RUBRIC (4 dimensions, integer scores 0-5 each)

COVERAGE
  0 — Omits nearly all key points from the source.
  3 — Covers main topic but misses one or two important supporting points.
  5 — Accurately captures all key points with appropriate emphasis.

FAITHFULNESS
  0 — Contains multiple claims that contradict or are absent from the source.
  3 — Mostly faithful; one minor unsupported inference or paraphrase.
  5 — Every claim is directly supported by the source document.

CONCISENESS
  0 — Severely over-compressed (loses critical meaning) or excessively verbose.
  3 — Mostly concise; minor redundancy or slight over-compression.
  5 — Appropriately dense: no filler, no repetition, no critical omissions.

STRUCTURE
  0 — No logical flow; ideas are jumbled or format is broken.
  3 — Recognisable structure but transitions are awkward or ordering is suboptimal.
  5 — Well-organised with clear logical flow and correct structured format.

PASS RULE: aggregate_score >= 3.5 AND hallucination_flag is False.
Hallucination (a claim not inferable from the source) is an automatic FAIL.
""".strip()

FAILURE_TAXONOMY = """
FAILURE TAG TAXONOMY (use only these exact tags):
  missed_key_point   — Summary omits a key point present in the source
  hallucinated_fact  — Summary asserts a fact not present in the source
  unsupported_claim  — Claim made without source evidence (weaker than hallucination)
  verbosity_excess   — Summary is unnecessarily verbose
  over_compression   — Summary loses too much detail
  poor_structure     — Summary is poorly organised
  topic_drift        — Summary shifts to off-topic content
  entity_error       — Named entities are misrepresented or confused
""".strip()
