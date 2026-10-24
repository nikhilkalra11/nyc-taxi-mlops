from pathlib import Path

import requests

BASE = "https://d37ci6vzurychx.cloudfront.net"


def source_urls(year: int, month: int) -> dict[str, str]:
    if not 2009 <= year <= 2100 or not 1 <= month <= 12:
        raise ValueError("Invalid year/month")
    return {
        "trips": f"{BASE}/trip-data/yellow_tripdata_{year}-{month:02d}.parquet",
        "zones": f"{BASE}/misc/taxi_zone_lookup.csv",
    }


def download(url: str, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 0:
        return target
    partial = target.with_name(target.name + ".part")
    try:
        with requests.get(url, stream=True, timeout=(15, 120)) as response:
            response.raise_for_status()
            with partial.open("wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        file.write(chunk)
        if partial.stat().st_size == 0:
            raise ValueError(f"Empty download: {url}")
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)
    return target
