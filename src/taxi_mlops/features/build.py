import numpy as np
import pandas as pd


def fare_features(trips: pd.DataFrame) -> pd.DataFrame:
    result = trips[["tpep_pickup_datetime", "PULocationID", "DOLocationID",
                    "trip_distance", "passenger_count", "fare_amount"]].copy()
    result["pickup_hour"] = result.tpep_pickup_datetime.dt.hour
    result["pickup_dayofweek"] = result.tpep_pickup_datetime.dt.dayofweek
    result["pickup_month"] = result.tpep_pickup_datetime.dt.month
    return result.sort_values("tpep_pickup_datetime").reset_index(drop=True)


def demand_features(trips: pd.DataFrame, year: int, month: int,
                    zones: pd.DataFrame) -> pd.DataFrame:
    if "LocationID" not in zones.columns:
        raise ValueError("Zone lookup requires LocationID")
    ids = sorted(set(pd.to_numeric(zones.LocationID, errors="coerce").dropna().astype(int))
                 & set(range(1, 264)))
    if not ids:
        raise ValueError("No valid zones in lookup")
    start = pd.Timestamp(year=year, month=month, day=1)
    end = start + pd.offsets.MonthBegin(1)
    hours = pd.date_range(start, end, freq="h", inclusive="left")
    index = pd.MultiIndex.from_product([ids, hours], names=["PULocationID", "hour"])
    events = trips.assign(hour=trips.tpep_pickup_datetime.dt.floor("h"))
    counts = events.groupby(["PULocationID", "hour"]).size().rename("demand")
    result = counts.reindex(index, fill_value=0).rename_axis(index.names).reset_index()
    result = result.sort_values(["PULocationID", "hour"]).reset_index(drop=True)
    groups = result.groupby("PULocationID", sort=False)["demand"]
    for lag in (1, 24, 168):
        result[f"lag_{lag}"] = groups.shift(lag)
    for window in (24, 168):
        result[f"rolling_mean_{window}"] = result.groupby("PULocationID", sort=False)["demand"].transform(
            lambda x: x.shift(1).rolling(window, min_periods=window).mean()
        )
    result["hour_of_day"] = result.hour.dt.hour
    result["day_of_week"] = result.hour.dt.dayofweek
    result["month"] = result.hour.dt.month
    return result.dropna().reset_index(drop=True)


def chronological_split(df: pd.DataFrame, time_column: str):
    ordered = df.sort_values(time_column).reset_index(drop=True)
    # Time-based boundaries avoid assigning the same timestamp to different splits.
    times = np.sort(ordered[time_column].unique())
    if len(times) < 10:
        raise ValueError("Insufficient unique timestamps for chronological split")
    a, b = times[int(len(times) * 0.8)], times[int(len(times) * 0.9)]
    return (ordered[ordered[time_column] < a].copy(),
            ordered[(ordered[time_column] >= a) & (ordered[time_column] < b)].copy(),
            ordered[ordered[time_column] >= b].copy())
