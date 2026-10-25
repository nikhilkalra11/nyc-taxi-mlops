"""Unit tests use a small in-memory fake S3 client (no AWS required)."""

import io
import json
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from taxi_mlops.lifecycle.registry import (
    RegistryError,
    build_manifest,
    read_version,
    register_version,
    sha256_bytes,
    validate_candidate_id,
)


class FakeS3:
    def __init__(self):
        self.objects = {}

    def get_object(self, *, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)])}

    def put_object(self, *, Bucket, Key, Body, ContentType, IfNoneMatch):
        assert IfNoneMatch == "*"
        if (Bucket, Key) in self.objects:
            raise ClientError({"Error": {"Code": "PreconditionFailed", "Message": "exists"}}, "PutObject")
        self.objects[(Bucket, Key)] = Body


def make_artifacts(root: Path):
    summary = {}
    for task in ("fare", "demand"):
        directory = root / task
        directory.mkdir(parents=True)
        model_bytes = (task + "-model").encode()
        (directory / "model.joblib").write_bytes(model_bytes)
        metadata = {
            "task": task, "winner": "lightgbm", "validation_rmse": 2.5,
            "test": {"rmse": 2.8}, "features": ["pickup_hour"],
            "model_sha256": sha256_bytes(model_bytes),
        }
        (directory / "metrics.json").write_text(json.dumps(metadata))
        summary[task] = metadata
    (root / "summary.json").write_text(json.dumps(summary))


def test_registration_round_trip(tmp_path):
    make_artifacts(tmp_path)
    manifest = build_manifest(
        candidate_id="retrain-001", artifact_root=tmp_path,
        bucket="test-bucket", feature_prefix="features",
        github_run_id="42", git_sha="a" * 40,
    )
    s3 = FakeS3()
    for relative, obj in manifest["artifacts"].items():
        s3.objects[("test-bucket", obj["key"])] = (tmp_path / relative).read_bytes()
    key = register_version(s3, manifest)
    assert key == "models/registry/versions/retrain-001.json"
    assert read_version(s3, "test-bucket", "retrain-001") == manifest
    with pytest.raises(RegistryError, match="already exists"):
        register_version(s3, manifest)


def test_remote_artifact_tampering_fails(tmp_path):
    make_artifacts(tmp_path)
    manifest = build_manifest(
        candidate_id="retrain-002", artifact_root=tmp_path,
        bucket="test-bucket", feature_prefix="features",
        github_run_id="42", git_sha="a" * 40,
    )
    s3 = FakeS3()
    for relative, obj in manifest["artifacts"].items():
        s3.objects[("test-bucket", obj["key"])] = (tmp_path / relative).read_bytes()
    key = manifest["artifacts"]["fare/model.joblib"]["key"]
    s3.objects[("test-bucket", key)] = b"tampered"
    with pytest.raises(RegistryError, match="mismatch"):
        register_version(s3, manifest)


@pytest.mark.parametrize("candidate_id", ["", "../escape", "with space", "a/b", ".."])
def test_invalid_candidate_id(candidate_id):
    with pytest.raises(ValueError):
        validate_candidate_id(candidate_id)


def test_wrong_candidate_id_type():
    with pytest.raises(TypeError):
        validate_candidate_id(42)


def test_manifest_detects_local_hash_mismatch(tmp_path):
    make_artifacts(tmp_path)
    (tmp_path / "fare" / "model.joblib").write_bytes(b"changed")
    with pytest.raises(RegistryError, match="SHA-256 mismatch"):
        build_manifest(
            candidate_id="retrain-003", artifact_root=tmp_path,
            bucket="test-bucket", feature_prefix="features",
            github_run_id="42", git_sha="a" * 40,
        )
