"""CloudWatch Embedded Metric Format (EMF) without PutMetricData permissions.

The existing ECS awslogs driver sends these JSON log records to CloudWatch Logs.
CloudWatch extracts metrics from valid EMF records automatically.
"""
from __future__ import annotations

import json
import logging
import time
import uuid

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("taxi.telemetry")
NAMESPACE = "NYCTaxi/Serving"


def metric_record(*, task: str, status: int, latency_ms: float, request_id: str) -> dict:
    """One request: count, error count and duration. Low-cardinality task dimension."""
    return {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [{
                "Namespace": NAMESPACE,
                "Dimensions": [["Task"]],
                "Metrics": [
                    {"Name": "Requests", "Unit": "Count"},
                    {"Name": "Errors", "Unit": "Count"},
                    {"Name": "Latency", "Unit": "Milliseconds"},
                ],
            }],
        },
        "Task": task,
        "Requests": 1,
        "Errors": int(status >= 500),
        "Latency": round(latency_ms, 3),
        "status_code": status,
        "request_id": request_id,
        "event": "prediction_request",
    }


class PredictionTelemetryMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/predict/"):
            return await call_next(request)
        task = request.url.path.removeprefix("/predict/")
        # Never log request bodies or customer-provided feature values.
        if task not in {"fare", "demand"}:
            task = "unknown"
        request_id = str(uuid.uuid4())
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            # Single-line JSON on stdout; awslogs sends it to CloudWatch Logs.
            logger.info(json.dumps(metric_record(
                task=task, status=status, latency_ms=elapsed_ms, request_id=request_id
            ), separators=(",", ":")))


def install_telemetry(app: FastAPI) -> None:
    app.add_middleware(PredictionTelemetryMiddleware)
