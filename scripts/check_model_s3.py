"""Verify exact S3 model keys expected by the ECS task."""
import argparse

import boto3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--prefix", default="training/local-run-001")
    args = parser.parse_args()
    s3 = boto3.client("s3")
    for task in ("fare", "demand"):
        for filename in ("model.joblib", "metrics.json"):
            key = f"{args.prefix.strip('/')}/{task}/{filename}"
            result = s3.head_object(Bucket=args.bucket, Key=key)
            print(f"OK s3://{args.bucket}/{key} ({result['ContentLength']} bytes)")


if __name__ == "__main__":
    main()
