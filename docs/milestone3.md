# Milestone 3 — Data lake and pipeline

## Prerequisites
Python 3.12, AWS CLI profile with S3 access, Terraform >=1.10.

## Install and test
```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
ruff check src tests scripts
pytest -q
```

## Provision S3
After extending the GitHub Terraform apply IAM role with scoped S3 permissions, run the existing Terraform Apply workflow. Alternatively, use your local AWS profile:
```bash
cd infrastructure/environments/dev
terraform init -backend-config="bucket=nyc-taxi-mlops-tfstate-ACCOUNT_ID"
terraform plan
terraform apply
terraform output -raw data_lake_bucket
```

## Execute
From repository root:
```bash
export AWS_PROFILE=taxi-dev
export TAXI_DATA_BUCKET=$(cd infrastructure/environments/dev && terraform output -raw data_lake_bucket)
python -m taxi_mlops.pipeline --config configs/data.yaml --output data
aws s3 ls "s3://$TAXI_DATA_BUCKET/" --recursive
```
To run without uploading, unset TAXI_DATA_BUCKET. January 2024 Yellow Taxi parquet may be large; have adequate RAM/disk. The full-month pipeline currently loads the file into memory. For a smaller-machine run, add chunked PyArrow processing in a later optimization.

## Important modeling caveats
Demand features currently omit the first 168 hours of the selected month to avoid using unknown prior-month history. To support operational predictions for those hours, load the preceding month and compute cross-month lag history. Fare features intentionally exclude post-trip measurements such as duration from predictors. Do not train on duration_minutes or total_amount for fare prediction.

## Expected outputs
- `data/raw/year=2024/month=01/` downloaded Parquet and zone CSV
- `data/processed/year=2024/month=01/trips_clean.parquet`
- `data/features/fare/year=2024/month=01/{train,validation,test}.parquet`
- `data/features/demand/year=2024/month=01/{train,validation,test}.parquet`
- `data/reports/year=2024/month=01/quality.json`

All uploaded objects use the same keys under the S3 bucket. Splits use timestamp boundaries, not random row sampling.
