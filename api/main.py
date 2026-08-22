from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException

from api.schemas import (
    CompleteStepOut,
    IncrementPartIn,
    PartOut,
    StepDetailOut,
    StepOut,
    ValidationReportOut,
)
from core import graph
from core.context import BuildContext
from core.models import Part, Step
from core.parser import load_build_data

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "rocket_build.json"

_context: BuildContext | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _context
    build_data = load_build_data(DATA_PATH)
    context = BuildContext(build_data)

    # Cycle detection before anything else runs: a cyclic graph makes every
    # downstream algorithm (topo sort, CPM, reachability) meaningless, so the
    # app should refuse to serve rather than return nonsense.
    cycle = graph.find_cycle(context)
    if cycle:
        raise RuntimeError(
            f"Step graph contains a cycle, refusing to start: {' -> '.join(cycle)}"
        )

    _context = context
    yield
    _context = None


def get_context() -> BuildContext:
    if _context is None:
        raise RuntimeError("Build context not initialized")
    return _context


app = FastAPI(title="Cerulean Beginnings", lifespan=lifespan)


def _step_out(context: BuildContext, step_id: str) -> StepOut:
    step = context.steps_by_id[step_id]
    return StepOut(
        id=step.id,
        name=step.name,
        instructions=step.instructions,
        required_parts=step.required_parts,
        required_prior_steps=step.required_prior_steps,
        duration_minutes=step.duration_minutes,
        complete=step.complete,
        status=graph.compute_step_status(context, step_id),
    )


def _get_step_or_404(context: BuildContext, step_id: str) -> Step:
    if step_id not in context.steps_by_id:
        raise HTTPException(status_code=404, detail=f"Unknown step id: {step_id}")
    return context.steps_by_id[step_id]


def _get_part_or_404(context: BuildContext, part_id: str) -> Part:
    if part_id not in context.parts_by_id:
        raise HTTPException(status_code=404, detail=f"Unknown part id: {part_id}")
    return context.parts_by_id[part_id]


@app.get("/steps", response_model=list[StepOut])
def list_steps(context: BuildContext = Depends(get_context)) -> list[StepOut]:
    return [_step_out(context, step.id) for step in context.build_data.steps]


@app.get("/steps/{step_id}", response_model=StepDetailOut)
def get_step(step_id: str, context: BuildContext = Depends(get_context)) -> StepDetailOut:
    _get_step_or_404(context, step_id)
    base = _step_out(context, step_id)
    return StepDetailOut(
        **base.model_dump(), dependents=graph.direct_dependents(context, step_id)
    )


@app.get("/steps/{step_id}/impact", response_model=list[str])
def get_step_impact(step_id: str, context: BuildContext = Depends(get_context)) -> list[str]:
    _get_step_or_404(context, step_id)
    return sorted(graph.downstream_impact(context, step_id))


@app.post("/steps/{step_id}/complete", response_model=CompleteStepOut)
def complete_step(step_id: str, context: BuildContext = Depends(get_context)) -> CompleteStepOut:
    step = _get_step_or_404(context, step_id)

    status = graph.compute_step_status(context, step_id)
    if status != "available":
        raise HTTPException(
            status_code=409,
            detail=f"Step '{step_id}' is not available (status: {status})",
        )

    for requirement in step.required_parts:
        part = context.parts_by_id[requirement.part_id]
        part.quantity_completed -= requirement.quantity
    step.complete = True

    newly_unlocked = [
        successor_id
        for successor_id in graph.direct_dependents(context, step_id)
        if graph.compute_step_status(context, successor_id) == "available"
    ]

    return CompleteStepOut(step=_step_out(context, step_id), newly_unlocked=newly_unlocked)


@app.post("/parts/{part_id}/increment", response_model=PartOut)
def increment_part(
    part_id: str, body: IncrementPartIn, context: BuildContext = Depends(get_context)
) -> PartOut:
    part = _get_part_or_404(context, part_id)
    new_quantity = part.quantity_completed + body.amount
    if new_quantity < 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Increment would take quantity_completed below 0 "
                f"(currently {part.quantity_completed})"
            ),
        )
    part.quantity_completed = new_quantity
    return PartOut(**part.model_dump())


@app.get("/build-order", response_model=list[str])
def get_build_order(context: BuildContext = Depends(get_context)) -> list[str]:
    return graph.topological_order(context)


@app.get("/validation", response_model=ValidationReportOut)
def get_validation(context: BuildContext = Depends(get_context)) -> ValidationReportOut:
    return ValidationReportOut(**graph.validate_structure(context))
