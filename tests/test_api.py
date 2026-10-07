"""API tests - require a trained champion model (run `make train` first)."""
import pytest

from src.common import config

pytestmark = pytest.mark.skipif(not (config.CHAMPION_DIR / "model.joblib").exists(),
                                reason="no champion model exported yet")


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    import os
    os.environ["PREDICTION_LOG"] = str(tmp_path_factory.mktemp("api") / "predictions.jsonl")
    import importlib

    import api.main as main
    importlib.reload(main)
    from fastapi.testclient import TestClient
    with TestClient(main.app) as c:
        yield c


def example():
    from api.main import StudentFeatures
    return dict(StudentFeatures.model_config["json_schema_extra"]["example"])


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_predict_weak_vs_strong(client):
    weak = client.post("/predict", json=example()).json()
    strong = client.post("/predict", json={**example(), "grade_p1": 17, "grade_p2": 18, "prior_failures": 0,
                                           "absences": 0, "study_time": 3}).json()
    assert 0 <= weak["fail_probability"] <= 1
    assert weak["fail_probability"] > strong["fail_probability"]
    assert strong["predicted_fail"] is False


def test_validation_error(client):
    assert client.post("/predict", json={**example(), "grade_p1": 25}).status_code == 422


def test_batch(client):
    r = client.post("/predict/batch", json=[example(), example()])
    assert r.status_code == 200 and len(r.json()) == 2
