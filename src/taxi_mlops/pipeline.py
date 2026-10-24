import argparse
import hashlib
import json
import os
from pathlib import Path

import boto3
import pandas as pd
import yaml

from taxi_mlops.features.build import chronological_split, demand_features, fare_features
from taxi_mlops.ingestion.download import download, source_urls
from taxi_mlops.validation.quality import clean_trips


def upload(file: Path, bucket: str, key: str) -> None:
    boto3.client("s3", region_name="us-east-1").upload_file(str(file), bucket, key)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(config_file: Path, output_dir: Path, bucket: str | None = None):
    cfg = yaml.safe_load(config_file.read_text())
    data_cfg = cfg["data"]
    year = int(data_cfg["year"])
    month = int(data_cfg["month"])
    partition = f"year={year}/month={month:02d}"
    raw_dir = output_dir / "raw" / partition
    urls = source_urls(year, month)
    trip_file = download(urls["trips"], raw_dir / f"yellow_tripdata_{year}-{month:02d}.parquet")
    zone_file = download(urls["zones"], raw_dir / "taxi_zone_lookup.csv")
    trips = pd.read_parquet(trip_file)
    zones = pd.read_csv(zone_file)
    validation_cfg = cfg["validation"]
    clean, quality = clean_trips(
        trips,
        year,
        month,
        validation_cfg,
    )
    artifacts = {"raw": [trip_file, zone_file]}
    clean_path = output_dir / "processed" / partition / "trips_clean.parquet"
    clean_path.parent.mkdir(parents=True, exist_ok=True)
    clean.to_parquet(clean_path, index=False)
    artifacts["processed"] = [clean_path]
    artifacts["features"] = []
    for name, frame, time_col in (
        ("fare", fare_features(clean), "tpep_pickup_datetime"),
        ("demand", demand_features(clean, year, month, zones), "hour"),
    ):
        if frame.empty:
            raise ValueError(f"Empty feature dataset: {name}")
        train, val, test = chronological_split(frame, time_col)
        for split, data in (("train", train), ("validation", val), ("test", test)):
            target = output_dir / "features" / name / partition / f"{split}.parquet"
            target.parent.mkdir(parents=True, exist_ok=True)
            data.to_parquet(target, index=False)
            artifacts["features"].append(target)
        quality[f"{name}_split_rows"] = {"train": len(train), "validation": len(val), "test": len(test)}
    quality["sources"] = urls
    quality["source_sha256"] = {"trips": sha256(trip_file), "zones": sha256(zone_file)}
    report = output_dir / "reports" / partition / "quality.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(quality, indent=2) + "\n")
    artifacts["reports"] = [report]
    if bucket:
        for files in artifacts.values():
            for file in files:
                upload(file, bucket, file.relative_to(output_dir).as_posix())
    print(json.dumps({"bucket": bucket, "report": str(report), **quality}, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/data.yaml"))
    parser.add_argument("--output", type=Path, default=Path("data"))
    parser.add_argument("--bucket", default=os.getenv("TAXI_DATA_BUCKET"))
    args = parser.parse_args()
    run(args.config, args.output, args.bucket)


if __name__ == "__main__":
    main()
