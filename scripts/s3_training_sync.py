"""Download features from Milestone 3 or upload trained model artifacts."""

import argparse
from pathlib import Path

import boto3


def transfer(bucket, prefix, directory, direction, region):
    s3 = boto3.client("s3", region_name=region)
    directory = Path(directory)
    prefix = prefix.strip("/") + "/"
    if direction == "download":
        count = 0
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if not key.endswith(".parquet"):
                    continue
                destination = directory / key.removeprefix(prefix)
                destination.parent.mkdir(parents=True, exist_ok=True)
                s3.download_file(bucket, key, str(destination))
                count += 1
        if not count:
            raise ValueError(f"No parquet files found at s3://{bucket}/{prefix}")
        print(f"Downloaded {count} files")
    else:
        files = [f for f in directory.rglob("*") if f.is_file()]
        if not files:
            raise ValueError(f"No artifacts found in {directory}")
        for file in files:
            key = prefix + file.relative_to(directory).as_posix()
            s3.upload_file(str(file), bucket, key)
            print(f"Uploaded s3://{bucket}/{key}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("direction", choices=["download", "upload"])
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args()
    transfer(args.bucket, args.prefix, args.directory, args.direction, args.region)


if __name__ == "__main__":
    main()
