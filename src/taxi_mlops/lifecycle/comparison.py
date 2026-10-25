"""Paired offline evaluation of registered candidate and deployed incumbent artifacts."""
from __future__ import annotations

import hashlib
import io
import json
import math
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from taxi_mlops.lifecycle.registry import read_version

TASKS = ("fare", "demand")


class ComparisonError(Exception):
    """Unsafe or invalid comparison inputs."""


def _download(s3, bucket, key):
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read()


def _load_model(raw, expected_sha=None):
    if expected_sha and hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ComparisonError("Model SHA-256 mismatch")
    # joblib/pickle is executable: only load trusted, access-controlled S3 artifacts.
    value = joblib.load(io.BytesIO(raw))
    if not isinstance(value, dict) or not {"model", "features", "target"} <= value.keys():
        raise ComparisonError("Unexpected model.joblib format")
    return value


def _score(model_bundle, frame):
    features = model_bundle["features"]
    target = model_bundle["target"]
    if not isinstance(features, list) or not features or not isinstance(target, str):
        raise ComparisonError("Invalid feature/target metadata")
    missing = set([*features, target]) - set(frame.columns)
    if missing:
        raise ComparisonError(f"Missing evaluation columns: {sorted(missing)}")
    subset = frame[[*features, target]].replace([np.inf, -np.inf], np.nan).dropna()
    if subset.empty:
        raise ComparisonError("No valid evaluation rows")
    x = subset[features].astype("float32")
    y = subset[target].astype("float32")
    prediction = np.asarray(model_bundle["model"].predict(x), dtype=float)
    if len(prediction) != len(y) or not np.isfinite(prediction).all():
        raise ComparisonError("Nonfinite or invalid predictions")
    return {"rmse": float(np.sqrt(mean_squared_error(y, prediction))),
            "mae": float(mean_absolute_error(y, prediction)), "rows": len(y),
            "row_indices": subset.index.tolist()}


def _registry_model(s3, record, task):
    descriptor = record["artifacts"][f"{task}/model.joblib"]
    raw = _download(s3, record["bucket"], descriptor["key"])
    return _load_model(raw, descriptor["sha256"])


def _incumbent_model(s3, bucket, prefix, task):
    raw = _download(s3, bucket, f"{prefix.rstrip('/')}/{task}/model.joblib")
    return _load_model(raw)


def compare_models(s3, *, bucket, candidate_id, incumbent_bucket, incumbent_prefix,
                   data_root, max_regression=0.0, min_improvement=0.0,
                   incumbent_task_definition=None):
    """Evaluate both bundles on identical rows; PASS only if both tasks meet thresholds.

    max_regression=0 means no RMSE degradation. min_improvement>0 requires a
    relative improvement for *each* task. They are mutually exclusive.
    """
    if not (0 <= max_regression < 1) or not (0 <= min_improvement < 1):
        raise ValueError("Thresholds must be between 0 (inclusive) and 1 (exclusive)")
    if max_regression and min_improvement:
        raise ValueError("Specify max_regression or min_improvement, not both")
    if not incumbent_prefix or not incumbent_bucket:
        raise ComparisonError("Incumbent S3 location is required")
    record = read_version(s3, bucket, candidate_id)
    if record.get("status") != "CANDIDATE" or record.get("candidate_id") != candidate_id:
        raise ComparisonError("Expected matching CANDIDATE registry record")
    result = {"schema_version": 1, "candidate_id": candidate_id,
              "candidate_registry_key": f"models/registry/versions/{candidate_id}.json",
              "incumbent": {"bucket": incumbent_bucket, "prefix": incumbent_prefix,
                            "ecs_task_definition": incumbent_task_definition},
              "evaluation_data_root": str(data_root),
              "thresholds": {"max_regression": max_regression,
                             "min_improvement": min_improvement},
              "created_at_utc": datetime.now(UTC).isoformat(), "tasks": {}}
    for task in TASKS:
        candidate = _registry_model(s3, record, task)
        incumbent = _incumbent_model(s3, incumbent_bucket, incumbent_prefix, task)
        if candidate["target"] != incumbent["target"]:
            raise ComparisonError(f"{task}: target mismatch")
        file = Path(data_root) / task / "year=2024" / "month=01" / "test.parquet"
        if not file.is_file():
            raise ComparisonError(f"Missing evaluation dataset: {file}")
        frame = pd.read_parquet(file)
        candidate_score = _score(candidate, frame)
        incumbent_score = _score(incumbent, frame)
        if candidate_score.pop("row_indices") != incumbent_score.pop("row_indices"):
            raise ComparisonError(f"{task}: models evaluated on different rows")
        old = incumbent_score["rmse"]
        if not math.isfinite(old) or old <= 0:
            raise ComparisonError(f"{task}: invalid incumbent RMSE")
        change = (candidate_score["rmse"] - old) / old
        passed = change <= (-min_improvement if min_improvement else max_regression)
        result["tasks"][task] = {"candidate": candidate_score, "incumbent": incumbent_score,
                                 "relative_rmse_change": change, "passed": passed,
                                 "evaluation_s3_key": None}
    result["decision"] = "PASS" if all(result["tasks"][t]["passed"] for t in TASKS) else "FAIL"
    return result


def write_report_once(s3, bucket, candidate_id, report):
    key = f"models/evaluations/{candidate_id}.json"
    try:
        s3.put_object(Bucket=bucket, Key=key,
                      Body=(json.dumps(report, indent=2, sort_keys=True) + "\n").encode(),
                      ContentType="application/json", IfNoneMatch="*")
    except Exception as exc:
        raise ComparisonError(f"Could not write evaluation report (possibly already exists): {key}") from exc
    return key
