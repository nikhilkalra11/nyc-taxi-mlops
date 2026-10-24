import pytest

from taxi_mlops.ingestion.download import source_urls


def test_source_urls():
    assert source_urls(2024, 1)["trips"].endswith("yellow_tripdata_2024-01.parquet")
    with pytest.raises(ValueError):
        source_urls(2024, 13)
