import pytest

from core.context import BuildContext
from core.graph import (
    compute_step_status,
    direct_dependents,
    downstream_impact,
    find_cycle,
    topological_order,
    validate_structure,
)
from core.models import Assembly, BuildData, Part, RequiredPart, Step
from core.parser import load_build_data

DATA_PATH = "data/rocket_build.json"


def make_step(id, required_prior_steps=None, required_parts=None, complete=False):
    return Step(
        id=id,
        name=id,
        instructions="",
        required_parts=required_parts or [],
        required_prior_steps=required_prior_steps or [],
        duration_minutes=10,
        complete=complete,
    )


def make_part(id, quantity_required=1, quantity_completed=0):
    return Part(
        id=id,
        name=id,
        material="test",
        cost_usd=1.0,
        lead_time_days=1,
        quantity_required=quantity_required,
        quantity_completed=quantity_completed,
    )


# ---- cycle detection ----


def test_find_cycle_detects_a_cycle():
    steps = [
        make_step("a", required_prior_steps=["c"]),
        make_step("b", required_prior_steps=["a"]),
        make_step("c", required_prior_steps=["b"]),
    ]
    context = BuildContext(BuildData(parts=[], steps=steps, assemblies=[]))

    cycle = find_cycle(context)

    assert cycle is not None
    assert set(cycle) == {"a", "b", "c"}


def test_find_cycle_returns_none_for_acyclic_graph():
    steps = [
        make_step("a"),
        make_step("b", required_prior_steps=["a"]),
    ]
    context = BuildContext(BuildData(parts=[], steps=steps, assemblies=[]))

    assert find_cycle(context) is None


def test_real_dataset_has_no_cycle():
    context = BuildContext(load_build_data(DATA_PATH))
    assert find_cycle(context) is None


# ---- topological sort ----


def test_topological_order_respects_dependencies():
    steps = [
        make_step("a"),
        make_step("b", required_prior_steps=["a"]),
        make_step("c", required_prior_steps=["a", "b"]),
    ]
    context = BuildContext(BuildData(parts=[], steps=steps, assemblies=[]))

    order = topological_order(context)
    position = {step_id: i for i, step_id in enumerate(order)}

    assert position["a"] < position["b"] < position["c"]


def test_real_dataset_topological_order_respects_all_priors():
    context = BuildContext(load_build_data(DATA_PATH))
    order = topological_order(context)
    position = {step_id: i for i, step_id in enumerate(order)}

    for step in context.build_data.steps:
        for prior_id in step.required_prior_steps:
            assert position[prior_id] < position[step.id]


# ---- reachability / dependents ----


def test_downstream_impact_is_transitive():
    steps = [
        make_step("a"),
        make_step("b", required_prior_steps=["a"]),
        make_step("c", required_prior_steps=["b"]),
        make_step("d"),  # unrelated branch
    ]
    context = BuildContext(BuildData(parts=[], steps=steps, assemblies=[]))

    assert downstream_impact(context, "a") == {"b", "c"}
    assert downstream_impact(context, "c") == set()


def test_direct_dependents_is_not_transitive():
    steps = [
        make_step("a"),
        make_step("b", required_prior_steps=["a"]),
        make_step("c", required_prior_steps=["b"]),
    ]
    context = BuildContext(BuildData(parts=[], steps=steps, assemblies=[]))

    assert direct_dependents(context, "a") == ["b"]


# ---- step status ----


def test_status_complete_when_flagged_complete():
    steps = [make_step("a", complete=True)]
    context = BuildContext(BuildData(parts=[], steps=steps, assemblies=[]))
    assert compute_step_status(context, "a") == "complete"


def test_status_blocked_when_prior_step_incomplete():
    steps = [
        make_step("a", complete=False),
        make_step("b", required_prior_steps=["a"]),
    ]
    context = BuildContext(BuildData(parts=[], steps=steps, assemblies=[]))
    assert compute_step_status(context, "b") == "blocked"


def test_status_blocked_when_part_quantity_insufficient():
    parts = [make_part("bolt", quantity_required=2, quantity_completed=1)]
    steps = [make_step("a", required_parts=[RequiredPart(part_id="bolt", quantity=2)])]
    context = BuildContext(BuildData(parts=parts, steps=steps, assemblies=[]))
    assert compute_step_status(context, "a") == "blocked"


def test_status_available_when_priors_done_and_parts_ready():
    parts = [make_part("bolt", quantity_required=2, quantity_completed=2)]
    steps = [
        make_step("a", complete=True),
        make_step(
            "b",
            required_prior_steps=["a"],
            required_parts=[RequiredPart(part_id="bolt", quantity=2)],
        ),
    ]
    context = BuildContext(BuildData(parts=parts, steps=steps, assemblies=[]))
    assert compute_step_status(context, "b") == "available"


def test_real_dataset_seeded_available_steps():
    context = BuildContext(load_build_data(DATA_PATH))
    expected_available = {"install-engine-mount", "attach-shock-cord", "attach-launch-lugs"}
    actual_available = {
        step.id
        for step in context.build_data.steps
        if compute_step_status(context, step.id) == "available"
    }
    assert actual_available == expected_available


# ---- structural validation ----


def test_validate_structure_reports_missing_part_ref():
    steps = [make_step("a", required_parts=[RequiredPart(part_id="ghost-part", quantity=1)])]
    context = BuildContext(BuildData(parts=[], steps=steps, assemblies=[]))

    report = validate_structure(context)

    assert report["missing_part_refs"] == [{"step_id": "a", "part_id": "ghost-part"}]


def test_validate_structure_reports_missing_step_ref():
    steps = [make_step("a", required_prior_steps=["ghost-step"])]
    context = BuildContext(BuildData(parts=[], steps=steps, assemblies=[]))

    report = validate_structure(context)

    assert report["missing_step_refs"] == [
        {"step_id": "a", "required_prior_step_id": "ghost-step"}
    ]


def test_validate_structure_reports_orphaned_part():
    parts = [make_part("unused-bolt")]
    context = BuildContext(BuildData(parts=parts, steps=[], assemblies=[]))

    report = validate_structure(context)

    assert report["orphaned_parts"] == ["unused-bolt"]


def test_real_dataset_validates_clean():
    context = BuildContext(load_build_data(DATA_PATH))
    report = validate_structure(context)
    assert report == {
        "cycles": [],
        "missing_part_refs": [],
        "missing_step_refs": [],
        "orphaned_parts": [],
    }
