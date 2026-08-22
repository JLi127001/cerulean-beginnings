from __future__ import annotations

from typing import Literal

import networkx as nx

from core.context import BuildContext

StepStatus = Literal["complete", "available", "blocked"]


def find_cycle(context: BuildContext) -> list[str] | None:
    """Return one cycle (as an ordered list of step ids) if the graph has one, else None.

    Must be checked before anything else runs -- topological_order() and every
    downstream algorithm (CPM, reachability) assumes a DAG and will misbehave or
    raise on a cyclic graph.
    """
    try:
        cycle_edges = nx.find_cycle(context.graph, orientation="original")
    except nx.NetworkXNoCycle:
        return None
    return [u for u, _v, _direction in cycle_edges]


def topological_order(context: BuildContext) -> list[str]:
    """A valid build order: every step appears after all of its required_prior_steps."""
    return list(nx.topological_sort(context.graph))


def downstream_impact(context: BuildContext, step_id: str) -> set[str]:
    """All steps transitively blocked if `step_id` slips (graph reachability)."""
    return set(nx.descendants(context.graph, step_id))


def direct_dependents(context: BuildContext, step_id: str) -> list[str]:
    """Steps whose required_prior_steps directly names step_id."""
    return list(context.graph.successors(step_id))


def compute_step_status(context: BuildContext, step_id: str) -> StepStatus:
    step = context.steps_by_id[step_id]
    if step.complete:
        return "complete"

    prior_steps_done = all(
        context.steps_by_id[prior_id].complete for prior_id in step.required_prior_steps
    )
    parts_ready = all(
        context.parts_by_id[req.part_id].quantity_completed >= req.quantity
        for req in step.required_parts
    )
    return "available" if prior_steps_done and parts_ready else "blocked"


def validate_structure(context: BuildContext) -> dict[str, list]:
    """Structural integrity report: cycles, dangling id references, unreferenced parts.

    Runs independently of whether the graph is a DAG -- even a cyclic or
    reference-broken build should still produce a readable report instead of
    crashing, so callers (e.g. GET /validation) can surface every problem at once.
    """
    cycle = find_cycle(context)

    missing_part_refs = [
        {"step_id": step.id, "part_id": req.part_id}
        for step in context.build_data.steps
        for req in step.required_parts
        if req.part_id not in context.parts_by_id
    ]

    missing_step_refs = [
        {"step_id": step.id, "required_prior_step_id": prior_id}
        for step in context.build_data.steps
        for prior_id in step.required_prior_steps
        if prior_id not in context.steps_by_id
    ]

    referenced_part_ids = {
        req.part_id for step in context.build_data.steps for req in step.required_parts
    }
    orphaned_parts = [
        part.id for part in context.build_data.parts if part.id not in referenced_part_ids
    ]

    return {
        "cycles": [cycle] if cycle else [],
        "missing_part_refs": missing_part_refs,
        "missing_step_refs": missing_step_refs,
        "orphaned_parts": orphaned_parts,
    }
