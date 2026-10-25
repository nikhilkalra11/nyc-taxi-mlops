"""Train and compare models without target leakage or random test splits."""

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import joblib
import mlflow
import numpy as np
import pandas as pd
import yaml
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor


def read_config(path):
    config = yaml.safe_load(Path(path).read_text())
    settings = config["training"]
    if settings["selection_metric"] != "validation_rmse":
        raise ValueError("Only validation_rmse model selection is supported")
    if not settings["models"] or not set(settings["models"]) <= {"lightgbm", "xgboost"}:
        raise ValueError("models must contain lightgbm and/or xgboost")
    for task in ("fare", "demand"):
        if not settings["features"].get(task) or not settings["target"].get(task):
            raise ValueError(f"Missing features/target for {task}")
    return config


def metrics(actual, predicted):
    return {
        "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
        "mae": float(mean_absolute_error(actual, predicted)),
        "r2": float(r2_score(actual, predicted)),
    }


def sample_frame(frame, limit, seed):
    """Deterministic subsample of training rows; preserve validation/test order."""
    if limit is None or len(frame) <= limit:
        return frame
    if limit < 1:
        raise ValueError("Sampling limit must be positive")
    return frame.sample(n=limit, random_state=seed).sort_index()


def load_split(directory, split, features, target, limit, seed):
    path = Path(directory) / f"{split}.parquet"
    frame = pd.read_parquet(path, columns=list(dict.fromkeys([*features, target])))
    frame = frame.replace([np.inf, -np.inf], np.nan).dropna(subset=[*features, target])
    frame = sample_frame(frame, limit, seed)
    if frame.empty:
        raise ValueError(f"Empty usable {split} dataset: {path}")
    return frame[features].astype("float32"), frame[target].astype("float32")


def make_model(name, params, seed):
    kwargs = {**params, "random_state": seed}
    if name == "lightgbm":
        return LGBMRegressor(**kwargs)
    if name == "xgboost":
        return XGBRegressor(objective="reg:squarederror", **kwargs)
    raise ValueError(f"Unsupported model: {name}")


def run_training(config_file, data_root, output_root, tasks=("fare", "demand")):
    config = read_config(config_file)
    settings = config["training"]
    seed = int(settings["seed"])
    mlflow.set_tracking_uri(
    os.environ.get(
        "MLFLOW_TRACKING_URI",
        "sqlite:///mlflow.db",
    )
)
    mlflow.set_experiment(settings["mlflow_experiment"])
    data_root, output_root = Path(data_root), Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    summary = {}

    for task in tasks:
        if task not in ("fare", "demand"):
            raise ValueError(f"Unsupported task: {task}")
        columns = settings["features"][task]
        target = settings["target"][task]
        directory = data_root / task
        # Milestone 3 stores splits under year=YYYY/month=MM.
        if not (directory / "train.parquet").exists():
            matches = sorted(directory.glob("year=*/month=*/train.parquet"))
            if len(matches) != 1:
                raise ValueError(
                    f"Expected exactly one partition under {directory}; found {len(matches)}. "
                    "Use --data-root with a single dataset partition."
                )
            directory = matches[0].parent
        # SageMaker mounts the three split files directly into its channel.
        if (data_root / "train.parquet").exists():
            directory = data_root
        limits = {
            "train": settings.get("max_training_rows"),
            "validation": settings.get("max_validation_rows"),
            "test": settings.get("max_test_rows"),
        }
        split = {
            name: load_split(directory, name, columns, target, limits[name], seed)
            for name in ("train", "validation", "test")
        }
        x_train, y_train = split["train"]
        x_val, y_val = split["validation"]
        x_test, y_test = split["test"]
        task_dir = output_root / task
        task_dir.mkdir(parents=True, exist_ok=True)
        candidates = []
        for name in settings["models"]:
            params = settings["hyperparameters"][name]
            with mlflow.start_run(run_name=f"{task}-{name}") as run:
                model = make_model(name, params, seed)
                model.fit(x_train, y_train)
                train_metrics = metrics(y_train, model.predict(x_train))
                validation_metrics = metrics(y_val, model.predict(x_val))
                mlflow.log_params({"task": task, "algorithm": name, "seed": seed, **params})
                mlflow.log_metrics({f"train_{k}": v for k, v in train_metrics.items()})
                mlflow.log_metrics({f"validation_{k}": v for k, v in validation_metrics.items()})
                mlflow.set_tags({"dataset": "nyc-tlc-yellow-taxi", "phase": "milestone4"})
                candidates.append((validation_metrics["rmse"], name, model, run.info.run_id))

        # Only the selected model is evaluated on test, once, after selection.
        candidates.sort(key=lambda candidate: (candidate[0], candidate[1]))
        _, winner_name, winner, winner_run = candidates[0]
        test_metrics = metrics(y_test, winner.predict(x_test))
        with mlflow.start_run(run_id=winner_run):
            mlflow.log_metrics({f"test_{k}": v for k, v in test_metrics.items()})
        artifact = task_dir / "model.joblib"
        joblib.dump({"model": winner, "features": columns, "target": target,
                     "task": task, "algorithm": winner_name}, artifact)
        metadata = {
            "task": task,
            "winner": winner_name,
            "selection_metric": "validation_rmse",
            "validation_rmse": candidates[0][0],
            "test": test_metrics,
            "candidates": [{"algorithm": name, "validation_rmse": score, "run_id": run_id}
                           for score, name, _, run_id in candidates],
            "rows": {name: len(split[name][0]) for name in split},
            "features": columns,
            "target": target,
            "model_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            "created_at_utc": datetime.now(UTC).isoformat(),
        }
        (task_dir / "metrics.json").write_text(json.dumps(metadata, indent=2) + "\n")
        summary[task] = metadata
    (output_root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary
