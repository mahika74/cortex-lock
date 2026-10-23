from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class DocumentRequest(StrictRequest):
    task_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=51200)


class MemoryRequest(StrictRequest):
    task_id: str = Field(min_length=1, max_length=128)
    run_id: str | None = None
    content: str = Field(min_length=1, max_length=8192)
    source_ids: list[str] = Field(min_length=1, max_length=64)
    derived_memory_ids: list[str] = Field(default_factory=list, max_length=64)
    idempotency_key: str = Field(min_length=1, max_length=128)


class RunRequest(StrictRequest):
    task_id: str = Field(min_length=1, max_length=128)
    scenario: Literal["normal", "injection"]
    mode: Literal["LIVE", "REPLAY"] = "LIVE"


class ResumeRequest(StrictRequest):
    pass
