"""Create a guarded, write-once model deployment approval record."""
import argparse
import json
import os
from pathlib import Path

import boto3

from taxi_mlops.lifecycle.promotion import approve_candidate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--cluster", required=True)
    parser.add_argument("--service", required=True)
    parser.add_argument("--output", type=Path, default=Path("artifacts/approvals/approval.json"))
    parser.add_argument("--max-age-hours", type=int, default=168)
    args = parser.parse_args()
    key, approval = approve_candidate(
        boto3.client("s3"), boto3.client("ecs"), bucket=args.bucket,
        candidate_id=args.candidate_id, cluster=args.cluster, service=args.service,
        github_run_id=os.environ["GITHUB_RUN_ID"], git_sha=os.environ["GITHUB_SHA"],
        max_age_hours=args.max_age_hours,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(approval, indent=2) + "\n", encoding="utf-8")
    print(f"Approval created: s3://{args.bucket}/{key}")
    print("ECS deployment unchanged. Phase 6 must revalidate approval and incumbent.")


if __name__ == "__main__":
    main()
