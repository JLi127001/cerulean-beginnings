from __future__ import annotations

from pydantic import BaseModel


class Part(BaseModel):
    id: str
    name: str
    material: str
    cost_usd: float
    lead_time_days: int
    quantity_required: int
    quantity_completed: int


class RequiredPart(BaseModel):
    part_id: str
    quantity: int


class Step(BaseModel):
    id: str
    name: str
    instructions: str
    required_parts: list[RequiredPart]
    required_prior_steps: list[str]
    duration_minutes: int
    complete: bool


class Assembly(BaseModel):
    id: str
    name: str
    step_ids: list[str]


class BuildData(BaseModel):
    parts: list[Part]
    steps: list[Step]
    assemblies: list[Assembly]
