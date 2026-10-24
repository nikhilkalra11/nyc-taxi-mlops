import pandas as pd

from taxi_mlops.features.build import chronological_split, demand_features


def test_demand_lag_does_not_use_current_hour():
    trips = pd.DataFrame({"PULocationID": [1, 1],
                          "tpep_pickup_datetime": pd.to_datetime(["2024-01-01 00:15", "2024-01-08 00:15"])})
    zones = pd.DataFrame({"LocationID": [1]})
    result = demand_features(trips, 2024, 1, zones)
    assert result.iloc[0]["hour"] == pd.Timestamp("2024-01-08 00:00")
    assert result.iloc[0]["lag_168"] == 1
    assert result.iloc[0]["demand"] == 1


def test_split_no_timestamp_overlap():
    df = pd.DataFrame({"hour": pd.date_range("2024-01-01", periods=100, freq="h")})
    a, b, c = chronological_split(df, "hour")
    assert a.hour.max() < b.hour.min() < c.hour.min()
