import pandas as pd

REQUIRED = {
    "tpep_pickup_datetime", "tpep_dropoff_datetime", "PULocationID",
    "DOLocationID", "trip_distance", "fare_amount", "passenger_count",
}


def clean_trips(df: pd.DataFrame, year: int, month: int, config: dict):
    missing = REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"Missing trip columns: {sorted(missing)}")
    input_rows = len(df)
    result = df.copy()
    for col in ("tpep_pickup_datetime", "tpep_dropoff_datetime"):
        result[col] = pd.to_datetime(result[col], errors="coerce")
    for col in ("PULocationID", "DOLocationID", "trip_distance", "fare_amount", "passenger_count"):
        result[col] = pd.to_numeric(result[col], errors="coerce")
    duration = (result.tpep_dropoff_datetime - result.tpep_pickup_datetime).dt.total_seconds() / 60
    mask = (
        result.tpep_pickup_datetime.notna()
        & result.tpep_dropoff_datetime.notna()
        & (result.tpep_pickup_datetime.dt.year == year)
        & (result.tpep_pickup_datetime.dt.month == month)
        & duration.between(1, config["max_duration_minutes"])
        & result.trip_distance.between(config["min_distance"], config["max_distance"])
        & result.fare_amount.between(config["min_fare"], config["max_fare"])
        & result.passenger_count.between(1, 8)
        & result.PULocationID.between(1, 263)
        & result.DOLocationID.between(1, 263)
    )
    cleaned = result.loc[mask].copy()
    cleaned["duration_minutes"] = duration.loc[mask]
    report = {"input_rows": int(input_rows), "valid_rows": len(cleaned),
              "rejected_rows": int(input_rows - len(cleaned)),
              "valid_ratio": round(len(cleaned) / input_rows, 5) if input_rows else 0}
    if cleaned.empty:
        raise ValueError("No valid trips remain after quality checks")
    return cleaned, report
