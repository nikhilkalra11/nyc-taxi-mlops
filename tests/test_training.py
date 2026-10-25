import numpy as np
import pandas as pd
import pytest

from taxi_mlops.training.core import metrics, read_config, sample_frame


def test_metrics_perfect_predictions():
    values = np.array([1.0, 2.0, 3.0])
    result = metrics(values, values)
    assert result["rmse"] == 0
    assert result["mae"] == 0
    assert result["r2"] == 1


def test_sampling_reproducible():
    frame = pd.DataFrame({"value": range(100)})
    a = sample_frame(frame, 10, 42)
    b = sample_frame(frame, 10, 42)
    pd.testing.assert_frame_equal(a, b)
    assert len(a) == 10


def test_sampling_rejects_zero():
    with pytest.raises(ValueError):
        sample_frame(pd.DataFrame({"x": range(3)}), 0, 42)


def test_training_config():
    cfg = read_config("configs/training.yaml")
    assert cfg["training"]["target"]["fare"] == "fare_amount"
