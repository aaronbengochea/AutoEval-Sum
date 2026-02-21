"""
Run lifecycle models.

RunStatus tracks every transition in the single-active-run + FIFO queue model.
RunRecord is the DynamoDB item stored in AutoEvalRuns.
RunConfig carries the per-run parameters decided at enqueue time.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    completed_with_errors = "completed_with_errors"
    failed = "failed"


class RunConfig(BaseModel):
    """Immutable parameters for a single run, set at enqueue time."""

    seed: int = Field(default=42)
    corpus_size: int = Field(default=150, ge=1)
    suite_size: int = Field(default=20, ge=1)


class RunRecord(BaseModel):
    """
    AutoEvalRuns DynamoDB item.

    pk = run_id  (no sort key — each run is a standalone entity)
    """

    run_id: str
    status: RunStatus
    config: RunConfig
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    error_message: str | None = None
    # Lightweight metrics snapshot written at finalization
    metrics_v1: dict[str, Any] | None = None
    metrics_v2: dict[str, Any] | None = None

    @classmethod
    def create(cls, run_id: str, config: RunConfig) -> "RunRecord":
        return cls(
            run_id=run_id,
            status=RunStatus.queued,
            config=config,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def to_dynamo_item(self) -> dict[str, Any]:
        data = self.model_dump()
        data["pk"] = self.run_id
        data["status"] = self.status.value
        data["config"] = self.config.model_dump()
        return data

    @classmethod
    def from_dynamo_item(cls, item: dict[str, Any]) -> "RunRecord":
        item = dict(item)
        item.pop("pk", None)
        return cls.model_validate(item)
