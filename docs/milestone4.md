# Milestone 4: Reproducible model training

## Integration rules

- **Overlay** these files on the existing Milestone 3 repository. Do not overwrite `pyproject.toml` with a replacement; apply the dependency additions below.
- Add the `training` package, scripts, config, and tests. Keep existing AWS Terraform and GitHub OIDC unchanged.
- The original Milestone 3 partition convention is `data/features/{fare|demand}/year=2024/month=01/{train|validation|test}.parquet`.
- **No SageMaker resources are deployed by default**. Managed training is opt-in and incurs charges.

## 1. pyproject.toml changes

Append the following to existing `[project].dependencies` (or extend its existing list):

```toml
"scikit-learn>=1.5,<2",
"lightgbm>=4.3,<5",
"xgboost>=2.1,<4",
"mlflow>=2.18,<4",
"joblib>=1.4,<2",
```

For optional SageMaker remote training, add a new extra under `[project.optional-dependencies]`:

```toml
aws-training = ["sagemaker>=2.220,<3"]
```

`pip install -e '.[dev]'` for local training, or `pip install -e '.[dev,aws-training]'` for optional SageMaker training.

## 2. Train locally

```bash
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q tests
python -m ruff check src tests scripts
python scripts/train_models.py --config configs/training.yaml --data-root data/features --output artifacts/models
mlflow ui --backend-store-uri ./mlruns --host 127.0.0.1 --port 5000
```

Open http://127.0.0.1:5000. Results: `artifacts/models/{fare,demand}/model.joblib`, `metrics.json`, `artifacts/models/summary.json`. No model is registered to a shared registry by default; the local MLflow runs contain metrics, parameters, and run IDs.

**Caution:** the fare features include `trip_distance` and `passenger_count`, which may not be known before pickup. This is a fare estimation baseline for supplied trip attributes, not a pre-trip quote. Demand lags are built from observed historical demand, and require updating when making future forecasts.

## 3. Sync features from S3 if needed

```bash
export AWS_PROFILE=taxi-dev AWS_DEFAULT_REGION=us-east-1
export TAXI_DATA_BUCKET="$(cd infrastructure/environments/dev && terraform output -raw data_lake_bucket)"
python scripts/s3_training_sync.py download --bucket "$TAXI_DATA_BUCKET" --prefix features/ --directory data/features
```

Then run the local training command. **The script expects one partition per task**. If you have multiple year/month partitions, place only the chosen partition under a dedicated data root or extend the script to accept a partition argument.

## 4. Upload local model artifacts to S3

```bash
python scripts/s3_training_sync.py upload --bucket "$TAXI_DATA_BUCKET" --prefix training/local-run-001/ --directory artifacts/models
aws s3 ls "s3://$TAXI_DATA_BUCKET/training/local-run-001/" --recursive
```

This uses local AWS credentials with `s3:ListBucket`, `s3:GetObject`, `s3:PutObject` as applicable. The GitHub Terraform deployment role is **not** used for model training.

## 5. Optional SageMaker managed training

### Prerequisites

1. `python -m pip install -e '.[dev,aws-training]'`
2. Create a SageMaker execution IAM role trusted by `sagemaker.amazonaws.com`, with scoped S3 read on `features/*`, S3 write on `training/sagemaker-output/*`, CloudWatch Logs write, and necessary ECR image pull permissions. Use a role you explicitly provision and review; do not reuse the Terraform apply role.
3. The **caller** also needs `sagemaker:CreateTrainingJob`, `sagemaker:DescribeTrainingJob`, and `iam:PassRole` restricted to the execution role. Add `s3:PutObject` for the SDK source-code upload path under the selected bucket.
4. The AWS SDK needs access to the managed SageMaker scikit-learn training image for your region and framework version. Validate the image availability before launching.

```bash
python scripts/launch_sagemaker.py \
  --task fare \
  --bucket "$TAXI_DATA_BUCKET" \
  --role-arn "arn:aws:iam::<ACCOUNT_ID>:role/<SAGEMAKER_EXECUTION_ROLE>" \
  --wait
```

Repeat with `--task demand`. Training jobs produce a `model.tar.gz` in `training/sagemaker-output/` and CloudWatch logs. The SageMaker training container installs `src/requirements.txt` and loads the training config copied into `src/configs/training.yaml`. **If you change `configs/training.yaml`, copy it to `src/configs/training.yaml` before launching remote training.**

MLflow tracking in this mode is **local to the training container**; the run store is not automatically uploaded or connected to a persistent MLflow server. Metrics JSON and model files are included in SageMaker's model archive. For persistent cross-job MLflow tracking, provision a managed MLflow tracking server in a later milestone and set its URI securely.

## 6. GitHub Actions CI

Your existing workflow already runs `pip install -e '.[dev]'`, `ruff check src tests scripts`, and `pytest -q tests`. Once the dependencies above are added, the new training unit tests run in the existing CI. Avoid running expensive model training in pull-request CI.

## 7. Evidence checklist

- `pytest -q tests` and Ruff green in PR CI
- Both fare and demand algorithms compared by validation RMSE
- MLflow experiment UI screenshot showing parameters and metrics
- `summary.json` and both task `metrics.json` saved
- S3 `training/local-run-001/` artifact listing
- Optional SageMaker job status, CloudWatch logs, and model artifact S3 URI
- Cleanup any SageMaker training jobs/notebooks/endpoints not required for the demo
