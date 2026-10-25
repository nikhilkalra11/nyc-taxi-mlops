"""CLI: register a successfully uploaded model candidate in S3."""

import argparse
import json
from pathlib import Path

from taxi_mlops.lifecycle.registry import (
    build_manifest,
    read_version,
    register_version,
    s3_client,
)


def main():
    parser = argparse.ArgumentParser(description="Write-once S3 model version registration")
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--artifact-root", type=Path, default=Path("artifacts/models"))
    parser.add_argument("--feature-prefix", required=True)
    parser.add_argument("--github-run-id", required=True)
    parser.add_argument("--git-sha", required=True)
    parser.add_argument("--output", type=Path, default=Path("artifacts/registry/version.json"))
    args = parser.parse_args()

    manifest = build_manifest(
        candidate_id=args.candidate_id,
        artifact_root=args.artifact_root,
        bucket=args.bucket,
        feature_prefix=args.feature_prefix,
        github_run_id=args.github_run_id,
        git_sha=args.git_sha,
    )
    s3 = s3_client()
    key = register_version(s3, manifest)
    remote = read_version(s3, args.bucket, args.candidate_id)
    if remote != manifest:
        raise RuntimeError("Registry read-back verification failed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Registered candidate: s3://{args.bucket}/{key}")
    print(f"Status: {remote['status']}")


if __name__ == "__main__":
    main()
