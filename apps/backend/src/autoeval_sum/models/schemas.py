"""
Agent I/O schemas.

All Pydantic models used as inputs and outputs for the four agents
(Summarizer, Eval Author, Judge, Curriculum).  Validators enforce the
word-count and item-count constraints from the holistic plan so that
malformed LLM output is caught immediately at parse time.
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ── Shared types ──────────────────────────────────────────────────────────────

FailureTag = Literal[
    "missed_key_point",
    "hallucinated_fact",
    "unsupported_claim",
    "verbosity_excess",
    "over_compression",
    "poor_structure",
    "topic_drift",
    "entity_error",
]

DifficultyTag = Literal["easy", "medium", "hard"]


# ── Summarizer output ─────────────────────────────────────────────────────────

class SummaryStructured(BaseModel):
    """
    Output of the Summarizer Agent.

    Constraints (enforced by validators):
    - exactly 5 key_points
    - each key_point <= 24 words
    - abstract <= 120 words
    """

    title: str = Field(..., min_length=1)
    key_points: Annotated[list[str], Field(min_length=5, max_length=5)]
    abstract: str = Field(..., min_length=1)

    @field_validator("key_points")
    @classmethod
    def validate_key_point_lengths(cls, points: list[str]) -> list[str]:
        for i, point in enumerate(points):
            word_count = len(point.split())
            if word_count > 24:
                raise ValueError(
                    f"key_points[{i}] has {word_count} words (max 24): {point!r}"
                )
        return points

    @field_validator("abstract")
    @classmethod
    def validate_abstract_length(cls, abstract: str) -> str:
        word_count = len(abstract.split())
        if word_count > 120:
            raise ValueError(f"abstract has {word_count} words (max 120)")
        return abstract


# ── Eval suite ────────────────────────────────────────────────────────────────

class EvalCase(BaseModel):
    """A single evaluation case produced by the Eval Author Agent."""

    eval_id: str = Field(..., description="Format: v{n}-case-{0001}")
    doc_id: str
    prompt_template: str = Field(..., min_length=1)
    constraints: dict[str, Any] = Field(default_factory=dict)
    rubric_note: str = Field(default="")
    difficulty_tag: DifficultyTag
    category_tag: str


# ── Rubric ────────────────────────────────────────────────────────────────────

class RubricAnchors(BaseModel):
    """Score anchors for a single rubric dimension."""

    score_0: str = Field(..., description="Description of a score-0 response")
    score_3: str = Field(..., description="Description of a score-3 response")
    score_5: str = Field(..., description="Description of a score-5 response")


class RubricGlobal(BaseModel):
    """
    Fixed four-dimension rubric used by the Judge Agent.
    Integer scores 0–5 per dimension; equal weights.
    """

    coverage: RubricAnchors
    faithfulness: RubricAnchors
    conciseness: RubricAnchors
    structure: RubricAnchors


# ── Judge output ──────────────────────────────────────────────────────────────

class ScoreCard(BaseModel):
    """Per-dimension integer scores from the Judge Agent."""

    coverage: int = Field(..., ge=0, le=5)
    faithfulness: int = Field(..., ge=0, le=5)
    conciseness: int = Field(..., ge=0, le=5)
    structure: int = Field(..., ge=0, le=5)

    @property
    def aggregate(self) -> float:
        return (self.coverage + self.faithfulness + self.conciseness + self.structure) / 4.0


class JudgeCaseResult(BaseModel):
    """
    Output of the Judge Agent for a single eval case.

    Pass rule: aggregate_score >= 3.5 AND hallucination_flag is False.
    Hallucination is an auto-fail regardless of aggregate.

    Constraints:
    - rationale   <= 60 words
    - evidence_spans <= 2 items
    - failure_tags must be from the fixed 8-tag taxonomy
    """

    model_config = ConfigDict(populate_by_name=True)

    eval_id: str
    scores: ScoreCard
    aggregate_score: float = Field(..., ge=0.0, le=5.0)
    hallucination_flag: bool
    failure_tags: list[FailureTag]
    rationale: str = Field(..., description="Judge rationale, max 60 words")
    evidence_spans: Annotated[list[str], Field(max_length=2)] = Field(default_factory=list)
    pass_result: bool = Field(..., alias="pass")

    @field_validator("rationale")
    @classmethod
    def validate_rationale_length(cls, rationale: str) -> str:
        word_count = len(rationale.split())
        if word_count > 60:
            raise ValueError(f"rationale has {word_count} words (max 60)")
        return rationale

    @model_validator(mode="after")
    def validate_pass_rule(self) -> "JudgeCaseResult":
        """
        Enforce: hallucination always overrides pass to False.
        If the LLM returns pass=True alongside hallucination_flag=True we
        correct it here so downstream metrics are always consistent.
        """
        if self.hallucination_flag and self.pass_result:
            self.pass_result = False
        return self

    @classmethod
    def compute_aggregate(cls, scores: ScoreCard) -> float:
        return round(scores.aggregate, 4)

    @classmethod
    def compute_pass(cls, aggregate: float, hallucination: bool) -> bool:
        return aggregate >= 3.5 and not hallucination


# ── Suite-level metrics ───────────────────────────────────────────────────────

class SuiteMetrics(BaseModel):
    """Aggregated metrics for a completed eval suite."""

    suite_id: str = Field(..., description="Format: {run_id}#v{n}")
    avg_scores_by_dimension: dict[str, float]
    aggregate_avg: float = Field(..., ge=0.0, le=5.0)
    pass_rate: float = Field(..., ge=0.0, le=1.0)
    failure_detection_rate: float = Field(..., ge=0.0, le=1.0)
    top_failure_modes: Annotated[list[str], Field(max_length=5)]
    worst_examples: Annotated[list[EvalCase], Field(max_length=5)]


# ── Curriculum output ─────────────────────────────────────────────────────────

class ImprovementPlan(BaseModel):
    """Human-readable diff plan produced by the Curriculum Agent."""

    retained_count: int = Field(..., ge=0)
    replaced_count: int = Field(..., ge=0)
    targeted_failure_modes: list[str]
    dedup_rejections: int = Field(..., ge=0)
    representative_changes: str = Field(..., min_length=1)


class CurriculumOutput(BaseModel):
    """Output of the Curriculum Agent — the v2 eval suite plus its rationale."""

    next_suite: list[EvalCase]
    improvement_plan: ImprovementPlan
