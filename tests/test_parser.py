from core.parser import load_build_data

DATA_PATH = "data/rocket_build.json"


def test_loads_expected_counts():
    build = load_build_data(DATA_PATH)
    assert len(build.parts) == 15
    assert len(build.steps) == 16
    assert len(build.assemblies) == 5


def test_step_required_parts_are_typed():
    build = load_build_data(DATA_PATH)
    attach_fins = next(s for s in build.steps if s.id == "attach-fins")
    assert [r.model_dump() for r in attach_fins.required_parts] == [
        {"part_id": "fin-set", "quantity": 4}
    ]


def test_every_required_part_id_exists_in_parts():
    build = load_build_data(DATA_PATH)
    part_ids = {p.id for p in build.parts}
    for step in build.steps:
        for req in step.required_parts:
            assert req.part_id in part_ids


def test_every_required_prior_step_id_exists_in_steps():
    build = load_build_data(DATA_PATH)
    step_ids = {s.id for s in build.steps}
    for step in build.steps:
        for prior_id in step.required_prior_steps:
            assert prior_id in step_ids
