import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_list_steps_includes_computed_status(client):
    resp = client.get("/steps")
    assert resp.status_code == 200
    steps_by_id = {s["id"]: s for s in resp.json()}

    assert steps_by_id["build-engine-mount"]["status"] == "complete"
    assert steps_by_id["install-engine-mount"]["status"] == "available"
    assert steps_by_id["attach-fins"]["status"] == "blocked"


def test_get_unknown_step_is_404(client):
    resp = client.get("/steps/does-not-exist")
    assert resp.status_code == 404


def test_get_step_detail_includes_dependents(client):
    resp = client.get("/steps/build-engine-mount")
    assert resp.status_code == 200
    assert resp.json()["dependents"] == ["install-engine-mount"]


def test_complete_step_rejects_when_not_available(client):
    resp = client.post("/steps/attach-fins/complete")
    assert resp.status_code == 409


def test_complete_step_consumes_parts_and_unlocks_successor(client):
    body_tube_before = client.get("/steps/install-engine-mount").json()["required_parts"]
    assert body_tube_before == [{"part_id": "body-tube", "quantity": 1}]

    resp = client.post("/steps/install-engine-mount/complete")
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["step"]["status"] == "complete"
    assert payload["newly_unlocked"] == ["attach-fins"]

    # part pool actually got consumed
    part_resp = client.post("/parts/body-tube/increment", json={"amount": 0})
    assert part_resp.json()["quantity_completed"] == 0


def test_increment_part_rejects_negative_overflow(client):
    resp = client.post("/parts/body-tube-decals/increment", json={"amount": -1})
    assert resp.status_code == 400


def test_increment_part_then_step_becomes_available(client):
    resp = client.get("/steps/apply-decals")
    assert resp.json()["status"] == "blocked"

    client.post("/parts/body-tube-decals/increment", json={"amount": 1})
    # apply-decals also needs paint-rocket done first, so it should still be blocked
    # on the prior-step requirement even though its own part is now ready
    resp = client.get("/steps/apply-decals")
    assert resp.json()["status"] == "blocked"


def test_build_order_is_a_valid_topological_order(client):
    resp = client.get("/build-order")
    order = resp.json()
    position = {step_id: i for i, step_id in enumerate(order)}

    steps = {s["id"]: s for s in client.get("/steps").json()}
    for step_id, step in steps.items():
        for prior_id in step["required_prior_steps"]:
            assert position[prior_id] < position[step_id]


def test_validation_report_is_clean_for_seed_dataset(client):
    resp = client.get("/validation")
    assert resp.json() == {
        "cycles": [],
        "missing_part_refs": [],
        "missing_step_refs": [],
        "orphaned_parts": [],
    }


def test_impact_of_early_step_reaches_final_inspection(client):
    resp = client.get("/steps/build-engine-mount/impact")
    assert "final-inspection" in resp.json()
