"""FastAPI inference for Milestone 4 joblib bundles."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

import boto3
import joblib
import numpy as np
import pandas as pd
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

LOG = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
TASKS = ("fare", "demand")


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    features: dict[str, float] = Field(min_length=1)


class PredictionResponse(BaseModel):
    task: Literal["fare", "demand"]
    prediction: float
    algorithm: str
    model_sha256: str


class ModelStore:
    def __init__(self) -> None:
        self.models: dict[str, dict[str, Any]] = {}
        self.meta: dict[str, dict[str, Any]] = {}

    def load(self, root: Path) -> None:
        loaded: dict[str, dict[str, Any]] = {}
        metadata: dict[str, dict[str, Any]] = {}
        for task in TASKS:
            artifact = root / task / "model.joblib"
            report = root / task / "metrics.json"
            if not artifact.is_file() or not report.is_file():
                raise FileNotFoundError(f"Missing {task} model or metadata in {root}")
            meta = json.loads(report.read_text())
            checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()
            if checksum != meta.get("model_sha256"):
                raise ValueError(f"SHA256 mismatch for {task} model")
            # joblib uses pickle internally. Load only artifacts you trained and trust.
            bundle = joblib.load(artifact)
            if not isinstance(bundle, dict) or not {"model", "features", "task", "algorithm"} <= bundle.keys():
                raise ValueError(f"Unexpected {task} model bundle format")
            if bundle["task"] != task or list(bundle["features"]) != list(meta["features"]):
                raise ValueError(f"Model metadata mismatch for {task}")
            loaded[task] = bundle
            metadata[task] = {**meta, "model_sha256": checksum}
        self.models, self.meta = loaded, metadata

    def predict(self, task: str, values: dict[str, float]) -> PredictionResponse:
        if task not in self.models:
            raise RuntimeError(f"Model {task} not loaded")
        bundle = self.models[task]
        expected = list(bundle["features"])
        missing = sorted(set(expected) - set(values))
        unexpected = sorted(set(values) - set(expected))
        if missing or unexpected:
            raise ValueError(f"Feature mismatch: missing={missing}; unexpected={unexpected}")
        if not all(np.isfinite(value) for value in values.values()):
            raise ValueError("All feature values must be finite")
        frame = pd.DataFrame([{feature: values[feature] for feature in expected}], columns=expected).astype("float32")
        value = float(bundle["model"].predict(frame)[0])
        if not np.isfinite(value):
            raise RuntimeError("Model returned a non-finite prediction")
        return PredictionResponse(
            task=task,
            prediction=max(0.0, value),  # Nonnegative fares and counts; raw score may be negative.
            algorithm=str(bundle["algorithm"]),
            model_sha256=self.meta[task]["model_sha256"],
        )


def download_models(bucket: str, prefix: str, destination: Path) -> None:
    s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))
    for task in TASKS:
        folder = destination / task
        folder.mkdir(parents=True, exist_ok=True)
        for filename in ("model.joblib", "metrics.json"):
            key = f"{prefix.strip('/')}/{task}/{filename}"
            LOG.info("Fetching s3://%s/%s", bucket, key)
            s3.download_file(bucket, key, str(folder / filename))


def make_app(store: ModelStore | None = None, load_on_start: bool = True) -> FastAPI:
    model_store = store or ModelStore()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if load_on_start:
            bucket = os.getenv("MODEL_BUCKET")
            prefix = os.getenv("MODEL_PREFIX", "training/local-run-001")
            local_root = os.getenv("MODEL_DIR")
            try:
                if bucket:
                    with tempfile.TemporaryDirectory(prefix="taxi-models-") as folder:
                        download_models(bucket, prefix, Path(folder))
                        model_store.load(Path(folder))
                elif local_root:
                    model_store.load(Path(local_root))
                else:
                    raise RuntimeError("Set MODEL_BUCKET or MODEL_DIR")
                LOG.info("Both models loaded successfully")
            except (OSError, ValueError, RuntimeError, ClientError, BotoCoreError):
                LOG.exception("Model initialization failed")
                raise
        yield

    app = FastAPI(title="NYC Taxi Prediction API", version="0.5.0", lifespan=lifespan)

    @app.get("/health/live")
    def live():
        return {"status": "alive"}

    @app.get("/health/ready")
    def ready():
        if set(model_store.models) != set(TASKS):
            raise HTTPException(status_code=503, detail="Models not ready")
        return {"status": "ready", "models": list(TASKS)}

    @app.get("/models")
    def models():
        if set(model_store.models) != set(TASKS):
            raise HTTPException(status_code=503, detail="Models not ready")
        return {
            task: {
                "algorithm": model_store.models[task]["algorithm"],
                "features": model_store.models[task]["features"],
                "sha256": model_store.meta[task]["model_sha256"],
            }
            for task in TASKS
        }

    @app.post("/predict/{task}", response_model=PredictionResponse)
    def predict(task: Literal["fare", "demand"], request: PredictionRequest):
        if task not in model_store.models:
            raise HTTPException(status_code=503, detail="Model not ready")
        try:
            return model_store.predict(task, request.features)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return app


app = make_app()
