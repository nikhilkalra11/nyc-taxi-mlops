"""Write-once S3 metadata registry for paired fare/demand model candidates."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

CANDIDATE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
TASKS = ("fare", "demand")


class RegistryError(Exception):
    """Invalid candidate metadata, artifact, or registration state."""


def validate_candidate_id(candidate_id: str) -> None:
    if not isinstance(candidate_id, str):
        raise TypeError("candidate_id must be a string")
    if not CANDIDATE_RE.fullmatch(candidate_id) or candidate_id in {".", ".."}:
        raise ValueError("candidate_id must be 1-80 safe characters (letters, digits, ._-)")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected JSON object: {path}")
    return value


def _metric(value: object, field: str) -> float:
    import math

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be numeric")
    if not math.isfinite(value):
        raise ValueError(f"{field} must be finite")
    return float(value)


def build_manifest(
    *, candidate_id: str, artifact_root: Path, bucket: str,
    feature_prefix: str, github_run_id: str, git_sha: str,
) -> dict:
    """Construct a manifest from local outputs produced by run_training()."""
    validate_candidate_id(candidate_id)
    if not bucket or not feature_prefix:
        raise ValueError("bucket and feature_prefix are required")
    root = Path(artifact_root)
    summary = _read_json(root / "summary.json")
    prefix = f"models/candidates/{candidate_id}"
    artifacts = {}
    models = {}
    for task in TASKS:
        metadata = _read_json(root / task / "metrics.json")
        model_path = root / task / "model.joblib"
        model_sha = sha256_bytes(model_path.read_bytes())
        if metadata.get("model_sha256") != model_sha:
            raise RegistryError(f"SHA-256 mismatch in {task}/metrics.json")
        if metadata.get("task") != task:
            raise RegistryError(f"Incorrect task in {task}/metrics.json")
        if summary.get(task) != metadata:
            raise RegistryError(f"summary.json disagrees with {task}/metrics.json")
        test = metadata.get("test")
        if not isinstance(test, dict):
            raise TypeError(f"{task}.test must be an object")
        models[task] = {
            "algorithm": metadata["winner"],
            "validation_rmse": _metric(metadata["validation_rmse"], f"{task}.validation_rmse"),
            "test_rmse": _metric(test["rmse"], f"{task}.test.rmse"),
            "features": metadata["features"],
            "model_sha256": model_sha,
        }
        for name in ("model.joblib", "metrics.json"):
            relative = f"{task}/{name}"
            content = (root / relative).read_bytes()
            artifacts[relative] = {
                "key": f"{prefix}/{relative}",
                "sha256": sha256_bytes(content),
                "size_bytes": len(content),
            }
    summary_bytes = (root / "summary.json").read_bytes()
    artifacts["summary.json"] = {
        "key": f"{prefix}/summary.json",
        "sha256": sha256_bytes(summary_bytes),
        "size_bytes": len(summary_bytes),
    }
    return {
        "schema_version": 1,
        "candidate_id": candidate_id,
        "status": "CANDIDATE",
        "registered_at_utc": datetime.now(UTC).isoformat(),
        "source": {
            "github_run_id": str(github_run_id),
            "git_sha": str(git_sha),
            "feature_prefix": feature_prefix.strip("/"),
        },
        "bucket": bucket,
        "artifact_prefix": prefix,
        "models": models,
        "artifacts": artifacts,
    }


def _get_object_bytes(s3, bucket: str, key: str) -> bytes:
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read()


def verify_remote_artifacts(s3, manifest: dict) -> None:
    """Verify remote bytes, not just object existence or ETag."""
    for name, artifact in manifest["artifacts"].items():
        try:
            content = _get_object_bytes(s3, manifest["bucket"], artifact["key"])
        except ClientError as exc:
            raise RegistryError(f"Unable to read candidate artifact: {name}") from exc
        if len(content) != artifact["size_bytes"] or sha256_bytes(content) != artifact["sha256"]:
            raise RegistryError(f"Remote candidate artifact mismatch: {name}")


def register_version(s3, manifest: dict) -> str:
    """Register exactly once using S3 conditional creation (no overwrites)."""
    validate_candidate_id(manifest["candidate_id"])
    verify_remote_artifacts(s3, manifest)
    key = f"models/registry/versions/{manifest['candidate_id']}.json"
    body = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        s3.put_object(
            Bucket=manifest["bucket"], Key=key, Body=body,
            ContentType="application/json", IfNoneMatch="*",
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"PreconditionFailed", "412", "ConditionalRequestConflict", "409"}:
            raise RegistryError(f"Registry version already exists or is being created: {key}") from exc
        raise
    return key


def read_version(s3, bucket: str, candidate_id: str) -> dict:
    validate_candidate_id(candidate_id)
    key = f"models/registry/versions/{candidate_id}.json"
    record = json.loads(_get_object_bytes(s3, bucket, key))
    if not isinstance(record, dict):
        raise TypeError("Registry record must be a JSON object")
    return record


def s3_client():
    return boto3.client("s3")
