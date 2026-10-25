import io
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from taxi_mlops.lifecycle.comparison import ComparisonError, compare_models, write_report_once


class FixedModel:
    def __init__(self, value):
        self.value = value

    def predict(self, x):
        return np.full(len(x), self.value)


class FakeS3:
    def __init__(self, objects):
        self.objects = objects

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)])}

    def put_object(self, Bucket, Key, Body, **kwargs):
        if (Bucket, Key) in self.objects:
            raise RuntimeError("exists")
        self.objects[(Bucket, Key)] = Body


def _bytes(value):
    buf = io.BytesIO()
    joblib.dump({"model": FixedModel(value), "features": ["x"], "target": "y"}, buf)
    return buf.getvalue()


def test_paired_comparison(tmp_path, monkeypatch):
    bucket, cid = "test-bucket", "candidate-001"
    objects = {}
    record = {"status": "CANDIDATE", "candidate_id": cid, "bucket": bucket, "artifacts": {}}
    import hashlib

    monkeypatch.setattr(pd, "read_parquet", lambda _: pd.DataFrame({"x": [1., 2., 3.], "y": [2., 2., 2.]}))
    for task in ("fare", "demand"):
        root = tmp_path / task / "year=2024" / "month=01"
        root.mkdir(parents=True)
        (root / "test.parquet").touch()
        new, old = _bytes(2), _bytes(3)
        key = f"models/candidates/{cid}/{task}/model.joblib"
        objects[(bucket, key)] = new
        objects[(bucket, f"production/models/{task}/model.joblib")] = old
        record["artifacts"][f"{task}/model.joblib"] = {
            "key": key, "sha256": hashlib.sha256(new).hexdigest()}
    s3 = FakeS3(objects)
    monkeypatch.setattr("taxi_mlops.lifecycle.comparison.read_version", lambda *args: record)
    result = compare_models(s3, bucket=bucket, candidate_id=cid,
                            incumbent_bucket=bucket, incumbent_prefix="production/models",
                            data_root=tmp_path)
    assert result["decision"] == "PASS"
    assert all(result["tasks"][task]["candidate"]["rmse"] == 0 for task in ("fare", "demand"))
    key = write_report_once(s3, bucket, cid, result)
    assert json.loads(objects[(bucket, key)])["decision"] == "PASS"
    with pytest.raises(ComparisonError):
        write_report_once(s3, bucket, cid, result)


def test_reject_missing_incumbent():
    with pytest.raises(ComparisonError):
        compare_models(None, bucket="b", candidate_id="c", incumbent_bucket="b",
                       incumbent_prefix="", data_root=Path("."))


def test_reject_conflicting_thresholds():
    with pytest.raises(ValueError):
        compare_models(None, bucket="b", candidate_id="c", incumbent_bucket="b",
                       incumbent_prefix="p", data_root=Path("."),
                       max_regression=.02, min_improvement=.01)
