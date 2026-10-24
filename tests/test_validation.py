import pandas as pd

from taxi_mlops.validation.quality import clean_trips


def test_cleaning_rejects_bad_fares():
    df = pd.DataFrame({
        "tpep_pickup_datetime": ["2024-01-02 10:00", "2024-01-02 10:00"],
        "tpep_dropoff_datetime": ["2024-01-02 10:15", "2024-01-02 10:15"],
        "PULocationID": [1, 1], "DOLocationID": [2, 2],
        "trip_distance": [2.0, 2.0], "fare_amount": [12.0, -1.0],
        "passenger_count": [1, 1],
    })
    cfg = {"max_duration_minutes": 240, "min_distance": 0.01,
           "max_distance": 100, "min_fare": 0.01, "max_fare": 500}
    clean, report = clean_trips(df, 2024, 1, cfg)
    assert len(clean) == 1
    assert report["rejected_rows"] == 1
