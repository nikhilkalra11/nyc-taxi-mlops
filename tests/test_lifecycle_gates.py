import pytest

from taxi_mlops.lifecycle.gates import evaluate


def test_both_improve():
    assert evaluate({'fare': {'rmse': 8}, 'demand': {'rmse': 12}},
                    {'fare': {'rmse': 10}, 'demand': {'rmse': 15}})['passed']


def test_one_regresses():
    assert not evaluate({'fare': {'rmse': 8}, 'demand': {'rmse': 16}},
                        {'fare': {'rmse': 10}, 'demand': {'rmse': 15}})['passed']


def test_missing_metrics_fail_closed():
    with pytest.raises(ValueError):
        evaluate({'fare': {'rmse': 8}}, {'fare': {'rmse': 10}, 'demand': {'rmse': 15}})
