"""Optional managed AWS training. Charges accrue while the training job runs."""

import argparse
import os

import boto3
from sagemaker.inputs import TrainingInput
from sagemaker.session import Session
from sagemaker.sklearn.estimator import SKLearn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=["fare", "demand"], required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--role-arn", required=True)
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--month", type=int, default=1)
    parser.add_argument("--instance-type", default="ml.m5.xlarge")
    parser.add_argument("--wait", action="store_true")
    args = parser.parse_args()
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    session = boto3.Session(region_name=region)
    # Only one task's three splits are mounted in /opt/ml/input/data/training.
    source_prefix = (f"s3://{args.bucket}/features/{args.task}/"
                     f"year={args.year}/month={args.month:02d}/")
    estimator = SKLearn(
        entry_point="taxi_mlops/training/sagemaker_entry.py",
        source_dir="src",
        role=args.role_arn,
        framework_version="1.2-1",
        py_version="py3",
        instance_count=1,
        instance_type=args.instance_type,
        volume_size=30,
        max_run=7200,
        output_path=f"s3://{args.bucket}/training/sagemaker-output/",
        hyperparameters={"task": args.task},
        sagemaker_session=Session(boto_session=session),
        base_job_name=f"nyc-taxi-{args.task}",
    )
    estimator.fit({"training": TrainingInput(source_prefix, input_mode="File")}, wait=args.wait)
    print(f"SageMaker job: {estimator.latest_training_job.name}")
    if args.wait:
        print(f"Model archive: {estimator.model_data}")


if __name__ == "__main__":
    main()
