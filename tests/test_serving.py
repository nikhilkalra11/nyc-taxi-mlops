import hashlib
import json

import joblib
from fastapi.testclient import TestClient

from taxi_mlops.serving.app import ModelStore, make_app


class FakeEstimator:
    def predict(self, frame):
        return [float(frame.iloc[0].sum())]


def test_model_load_and_api(tmp_path):
    for task in ("fare", "demand"):
        folder = tmp_path / task
        folder.mkdir()
        model_path = folder / "model.joblib"
        joblib.dump({"model": FakeEstimator(), "features": ["a", "b"], "task": task, "algorithm": "fake"}, model_path)
        (folder / "metrics.json").write_text(json.dumps({"features": ["a", "b"], "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest()}))
    store = ModelStore()
    store.load(tmp_path)
    with TestClient(make_app(store=store, load_on_start=False)) as client:
        assert client.get("/health/ready").status_code == 200
        assert client.get("/models").status_code == 200
        response = client.post("/predict/fare", json={"features": {"b": 2, "a": 3}})
        assert response.status_code == 200
        assert response.json()["prediction"] == 5
        assert client.post("/predict/fare", json={"features": {"a": 1}}).status_code == 422
        assert client.post("/predict/fare", json={"features": {"a": 1, "b": 2, "c": 3}}).status_code == 422


def test_not_ready():
    with TestClient(make_app(store=ModelStore(), load_on_start=False)) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503
