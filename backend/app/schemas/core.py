from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskRequest(StrictModel):
    agent_id: str = Field(min_length=1, max_length=128)
    template_id: Literal["SALES_INTERNAL", "SALES_EXTERNAL_REVIEW"]


class ActionRequest(StrictModel):
    task_id: str = Field(min_length=1, max_length=128)
    run_id: str | None = None
    tool: str = Field(min_length=1, max_length=64)
    args: dict
    memory_ids: list[str] = Field(default_factory=list, max_length=64)
    source_ids: list[str] = Field(default_factory=list, max_length=64)
    idempotency_key: str = Field(min_length=1, max_length=128)


class ExecuteRequest(StrictModel):
    action_id: str


class ApprovalDecision(StrictModel):
    decision: Literal["ALLOW_ONCE", "DENY"]
