from __future__ import annotations

from pydantic import BaseModel

from core.graph import StepStatus
from core.models import RequiredPart


class PartOut(BaseModel):
    id: str
    name: str
    material: str
    cost_usd: float
    lead_time_days: int
    quantity_required: int
    quantity_completed: int


class StepOut(BaseModel):
    id: str
    name: str
    instructions: str
    required_parts: list[RequiredPart]
    required_prior_steps: list[str]
    duration_minutes: int
    complete: bool
    status: StepStatus


class StepDetailOut(StepOut):
    dependents: list[str]


class CompleteStepOut(BaseModel):
    step: StepOut
    newly_unlocked: list[str]


class IncrementPartIn(BaseModel):
    amount: int


class ValidationReportOut(BaseModel):
    cycles: list[list[str]]
    missing_part_refs: list[dict]
    missing_step_refs: list[dict]
    orphaned_parts: list[str]
