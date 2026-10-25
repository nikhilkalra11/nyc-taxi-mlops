import json

from taxi_mlops.observability.telemetry import NAMESPACE, metric_record


def test_emf_record_schema():
    record = metric_record(task="fare", status=200, latency_ms=12.34, request_id="test-id")
    assert record["_aws"]["CloudWatchMetrics"][0]["Namespace"] == NAMESPACE
    assert record["Requests"] == 1
    assert record["Errors"] == 0
    assert record["Task"] == "fare"
    assert json.loads(json.dumps(record)) == record


def test_emf_server_error():
    record = metric_record(task="demand", status=503, latency_ms=2, request_id="x")
    assert record["Errors"] == 1
