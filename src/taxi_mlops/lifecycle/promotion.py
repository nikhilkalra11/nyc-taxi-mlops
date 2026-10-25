"""Fail-closed approval evidence gate; does not deploy or mutate model versions."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime, timedelta

from botocore.exceptions import ClientError

from taxi_mlops.lifecycle.registry import read_version, validate_candidate_id

TASKS = ("fare", "demand")


class PromotionError(Exception):
    """Promotion approval prerequisites have not been met."""


def _get(s3, bucket: str, key: str) -> bytes:
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read()


def _json_object(raw: bytes, label: str) -> dict:
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise PromotionError(f"Invalid JSON: {label}") from exc
    if not isinstance(value, dict):
        raise PromotionError(f"Expected JSON object: {label}")
    return value


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise PromotionError("Missing evaluation timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise PromotionError("Invalid evaluation timestamp") from exc
    if parsed.tzinfo is None:
        raise PromotionError("Evaluation timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


def _verify_candidate(s3, bucket: str, candidate_id: str) -> tuple[dict, str]:
    key = f"models/registry/versions/{candidate_id}.json"
    raw = _get(s3, bucket, key)
    record = _json_object(raw, key)
    if record != read_version(s3, bucket, candidate_id):
        raise PromotionError("Registry read mismatch")
    if (record.get("candidate_id") != candidate_id or record.get("status") != "CANDIDATE"
            or record.get("bucket") != bucket):
        raise PromotionError("Registry candidate identity or status mismatch")
    descriptors = record.get("artifacts")
    if not isinstance(descriptors, dict):
        raise PromotionError("Missing registry artifact descriptors")
    for task in TASKS:
        if task not in record.get("models", {}):
            raise PromotionError(f"Missing registry model: {task}")
    for name in ("summary.json", *(f"{t}/{f}" for t in TASKS for f in ("model.joblib", "metrics.json"))):
        desc = descriptors.get(name)
        if not isinstance(desc, dict):
            raise PromotionError(f"Missing artifact descriptor: {name}")
        expected_key = f"models/candidates/{candidate_id}/{name}"
        if desc.get("key") != expected_key:
            raise PromotionError(f"Artifact key mismatch: {name}")
        data = _get(s3, bucket, expected_key)
        if hashlib.sha256(data).hexdigest() != desc.get("sha256") or len(data) != desc.get("size_bytes"):
            raise PromotionError(f"Artifact changed since registration: {name}")
    return record, hashlib.sha256(raw).hexdigest()


def _verify_report(report: dict, candidate_id: str, bucket: str, incumbent_prefix: str,
                   task_definition: str, now: datetime, max_age_hours: int) -> None:
    if report.get("candidate_id") != candidate_id or report.get("decision") != "PASS":
        raise PromotionError("Evaluation candidate mismatch or decision not PASS")
    if report.get("candidate_registry_key") != f"models/registry/versions/{candidate_id}.json":
        raise PromotionError("Evaluation references a different registry version")
    incumbent = report.get("incumbent")
    if not isinstance(incumbent, dict) or (incumbent.get("bucket") != bucket
            or incumbent.get("prefix", "").rstrip("/") != incumbent_prefix.rstrip("/")
            or incumbent.get("ecs_task_definition") != task_definition):
        raise PromotionError("Evaluation incumbent identity differs from live ECS")
    timestamp = _timestamp(report.get("created_at_utc"))
    if timestamp > now + timedelta(minutes=5) or now - timestamp > timedelta(hours=max_age_hours):
        raise PromotionError("Evaluation is stale or dated in the future")
    results = report.get("tasks")
    if not isinstance(results, dict):
        raise PromotionError("Missing per-task evaluation")
    for task in TASKS:
        item = results.get(task)
        if not isinstance(item, dict) or item.get("passed") is not True:
            raise PromotionError(f"{task} did not pass evaluation")
        candidate = item.get("candidate", {})
        incumbent_score = item.get("incumbent", {})
        for score in (candidate, incumbent_score):
            if not isinstance(score, dict) or not isinstance(score.get("rmse"), (int, float)):
                raise PromotionError(f"Missing RMSE for {task}")
            if isinstance(score["rmse"], bool) or not math.isfinite(score["rmse"]) or score["rmse"] <= 0:
                raise PromotionError(f"Invalid RMSE for {task}")
            if not isinstance(score.get("rows"), int) or isinstance(score["rows"], bool) or score["rows"] <= 0:
                raise PromotionError(f"Invalid row count for {task}")
        if candidate["rows"] != incumbent_score["rows"]:
            raise PromotionError(f"Different evaluation row counts for {task}")
        change = (candidate["rmse"] - incumbent_score["rmse"]) / incumbent_score["rmse"]
        threshold = report.get("thresholds", {})
        if not isinstance(threshold, dict):
            raise PromotionError("Missing thresholds")
        max_reg = threshold.get("max_regression")
        min_imp = threshold.get("min_improvement")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v < 1
               for v in (max_reg, min_imp)) or (max_reg and min_imp):
            raise PromotionError("Invalid evaluation thresholds")
        if change > (-min_imp if min_imp else max_reg) + 1e-12:
            raise PromotionError(f"{task} RMSE violates reported threshold")
        if not math.isclose(change, item.get("relative_rmse_change", float("nan")), abs_tol=1e-9):
            raise PromotionError(f"{task} relative RMSE mismatch")


def _live_ecs(ecs, cluster: str, service: str) -> tuple[str, str, str]:
    result = ecs.describe_services(cluster=cluster, services=[service])
    services = result.get("services", [])
    if len(services) != 1 or services[0].get("status") != "ACTIVE":
        raise PromotionError("ECS service missing or inactive")
    definition_arn = services[0]["taskDefinition"]
    definition = ecs.describe_task_definition(taskDefinition=definition_arn)["taskDefinition"]
    envs = [item for container in definition["containerDefinitions"]
            for item in container.get("environment", [])]
    buckets = {item["value"] for item in envs if item["name"] == "MODEL_BUCKET"}
    prefixes = {item["value"] for item in envs if item["name"] == "MODEL_PREFIX"}
    if len(buckets) != 1 or len(prefixes) != 1:
        raise PromotionError("Cannot uniquely resolve MODEL_BUCKET and MODEL_PREFIX from ECS")
    return definition_arn, buckets.pop(), prefixes.pop()


def approve_candidate(s3, ecs, *, bucket: str, candidate_id: str, cluster: str,
                      service: str, github_run_id: str, git_sha: str,
                      max_age_hours: int = 168, now: datetime | None = None) -> tuple[str, dict]:
    """Validate PASS and current incumbent, then create an approval record once.

    This is authorization evidence for a later deployment, not a deployment itself.
    """
    validate_candidate_id(candidate_id)
    if max_age_hours < 1:
        raise ValueError("max_age_hours must be positive")
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    task_def, incumbent_bucket, incumbent_prefix = _live_ecs(ecs, cluster, service)
    if incumbent_bucket != bucket:
        raise PromotionError("Live ECS model bucket differs from registry bucket")
    record, registry_sha = _verify_candidate(s3, bucket, candidate_id)
    report_key = f"models/evaluations/{candidate_id}.json"
    report_raw = _get(s3, bucket, report_key)
    report = _json_object(report_raw, report_key)
    _verify_report(report, candidate_id, bucket, incumbent_prefix, task_def, now, max_age_hours)
    key = f"models/approvals/{candidate_id}.json"
    approval = {
        "schema_version": 1,
        "candidate_id": candidate_id,
        "status": "APPROVED_FOR_DEPLOYMENT",
        "approved_at_utc": now.astimezone(UTC).isoformat(),
        "approval_workflow_run_id": str(github_run_id),
        "approval_workflow_git_sha": str(git_sha),
        "registry": {"key": f"models/registry/versions/{candidate_id}.json", "sha256": registry_sha},
        "evaluation": {"key": report_key, "sha256": hashlib.sha256(report_raw).hexdigest()},
        "incumbent": {"bucket": incumbent_bucket, "prefix": incumbent_prefix,
                      "ecs_cluster": cluster, "ecs_service": service,
                      "ecs_task_definition": task_def},
        "candidate_artifact_prefix": record["artifact_prefix"],
    }
    body = (json.dumps(approval, indent=2, sort_keys=True) + "\n").encode()
    try:
        s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json", IfNoneMatch="*")
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"PreconditionFailed", "412", "ConditionalRequestConflict", "409"}:
            raise PromotionError("Approval already exists or is being written") from exc
        raise
    return key, approval
