"""Offline candidate/incumbent evaluation; never modifies ECS or model pointers."""
import argparse
import json
from pathlib import Path

import boto3

from taxi_mlops.lifecycle.comparison import compare_models, write_report_once


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--incumbent-bucket", required=True)
    parser.add_argument("--incumbent-prefix", required=True)
    parser.add_argument("--incumbent-task-definition")
    parser.add_argument("--data-root", type=Path, default=Path("data/features"))
    parser.add_argument("--max-regression", type=float, default=0.0)
    parser.add_argument("--min-improvement", type=float, default=0.0)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evaluations/report.json"))
    args = parser.parse_args()
    s3 = boto3.client("s3")
    report = compare_models(s3, bucket=args.bucket, candidate_id=args.candidate_id,
                            incumbent_bucket=args.incumbent_bucket,
                            incumbent_prefix=args.incumbent_prefix,
                            data_root=args.data_root,
                            max_regression=args.max_regression,
                            min_improvement=args.min_improvement,
                            incumbent_task_definition=args.incumbent_task_definition)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    key = write_report_once(s3, args.bucket, args.candidate_id, report)
    print(f"Evaluation: {report['decision']}; s3://{args.bucket}/{key}")
    for task, result in report["tasks"].items():
        print(f"{task}: incumbent={result['incumbent']['rmse']:.4f}, "
              f"candidate={result['candidate']['rmse']:.4f}, "
              f"relative_change={result['relative_rmse_change']:+.2%}")
    if report["decision"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
