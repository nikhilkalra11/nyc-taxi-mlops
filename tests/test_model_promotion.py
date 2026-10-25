import hashlib
import json
from datetime import UTC, datetime
from io import BytesIO

import pytest
from botocore.exceptions import ClientError

from taxi_mlops.lifecycle.promotion import PromotionError, approve_candidate

BUCKET = "test-bucket"
CID = "candidate-001"
TASK_DEF = "arn:aws:ecs:us-east-1:123456789012:task-definition/api:5"
PREFIX = "training/local-run-001"
NOW = datetime(2026, 10, 25, 12, tzinfo=UTC)


class FakeS3:
    def __init__(self, objects):
        self.objects = objects

    def get_object(self, Bucket, Key):
        return {"Body": BytesIO(self.objects[(Bucket, Key)])}

    def put_object(self, Bucket, Key, Body, **kwargs):
        if (Bucket, Key) in self.objects:
            raise ClientError({"Error": {"Code": "PreconditionFailed", "Message": "exists"}}, "PutObject")
        self.objects[(Bucket, Key)] = Body


class FakeECS:
    def __init__(self, prefix=PREFIX, task_def=TASK_DEF):
        self.prefix = prefix
        self.task_def = task_def

    def describe_services(self, cluster, services):
        return {"services": [{"status": "ACTIVE", "taskDefinition": self.task_def}]}

    def describe_task_definition(self, taskDefinition):
        return {"taskDefinition": {"containerDefinitions": [{"environment": [
            {"name": "MODEL_BUCKET", "value": BUCKET},
            {"name": "MODEL_PREFIX", "value": self.prefix},
        ]}]}}


def fixtures():
    objects = {}
    artifacts = {}
    for name in ["summary.json", "fare/model.joblib", "fare/metrics.json", "demand/model.joblib", "demand/metrics.json"]:
        content = name.encode()
        key = f"models/candidates/{CID}/{name}"
        objects[(BUCKET, key)] = content
        artifacts[name] = {"key": key, "sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content)}
    record = {"candidate_id": CID, "status": "CANDIDATE", "bucket": BUCKET,
              "artifact_prefix": f"models/candidates/{CID}", "artifacts": artifacts,
              "models": {"fare": {}, "demand": {}}}
    objects[(BUCKET, f"models/registry/versions/{CID}.json")] = json.dumps(record).encode()
    tasks = {t: {"passed": True, "candidate": {"rmse": 9.0, "rows": 100},
                 "incumbent": {"rmse": 10.0, "rows": 100},
                 "relative_rmse_change": -0.1} for t in ("fare", "demand")}
    report = {"candidate_id": CID, "decision": "PASS",
              "candidate_registry_key": f"models/registry/versions/{CID}.json",
              "incumbent": {"bucket": BUCKET, "prefix": PREFIX, "ecs_task_definition": TASK_DEF},
              "created_at_utc": NOW.isoformat(),
              "thresholds": {"max_regression": 0.0, "min_improvement": 0.0},
              "tasks": tasks}
    objects[(BUCKET, f"models/evaluations/{CID}.json")] = json.dumps(report).encode()
    return FakeS3(objects), report


def approve(s3, ecs=None):
    return approve_candidate(s3, ecs or FakeECS(), bucket=BUCKET, candidate_id=CID,
                             cluster="cluster", service="api", github_run_id="123", git_sha="abc", now=NOW)


def test_success():
    s3, _ = fixtures()
    key, record = approve(s3)
    assert key == f"models/approvals/{CID}.json"
    assert record["status"] == "APPROVED_FOR_DEPLOYMENT"
    assert record["incumbent"]["ecs_task_definition"] == TASK_DEF


def test_duplicate_rejected():
    s3, _ = fixtures()
    approve(s3)
    with pytest.raises(PromotionError, match="already exists"):
        approve(s3)


def test_failed_evaluation_rejected():
    s3, report = fixtures()
    report["decision"] = "FAIL"
    s3.objects[(BUCKET, f"models/evaluations/{CID}.json")] = json.dumps(report).encode()
    with pytest.raises(PromotionError, match="not PASS"):
        approve(s3)


def test_wrong_live_incumbent_rejected():
    s3, _ = fixtures()
    with pytest.raises(PromotionError, match="incumbent identity"):
        approve(s3, FakeECS(prefix="some-other-prefix"))


def test_artifact_tampering_rejected():
    s3, _ = fixtures()
    s3.objects[(BUCKET, f"models/candidates/{CID}/fare/model.joblib")] = b"tampered"
    with pytest.raises(PromotionError, match="Artifact changed"):
        approve(s3)


def test_wrong_task_definition_rejected():
    s3, _ = fixtures()
    with pytest.raises(PromotionError, match="incumbent identity"):
        approve(s3, FakeECS(task_def="different-task-definition"))


def test_stale_evaluation_rejected():
    s3, report = fixtures()
    report["created_at_utc"] = "2025-01-01T00:00:00+00:00"
    s3.objects[(BUCKET, f"models/evaluations/{CID}.json")] = json.dumps(report).encode()
    with pytest.raises(PromotionError, match="stale"):
        approve(s3)


def test_forged_pass_task_rejected():
    s3, report = fixtures()
    report["tasks"]["fare"]["candidate"]["rmse"] = 15.0
    s3.objects[(BUCKET, f"models/evaluations/{CID}.json")] = json.dumps(report).encode()
    with pytest.raises(PromotionError, match="violates"):
        approve(s3)
