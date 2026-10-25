# Milestone 5 — NYC Taxi Serving

## Design / integration contract

This overlay assumes the exact Milestone 4 artifact contract:
- S3 `training/local-run-001/fare/{model.joblib,metrics.json}`
- S3 `training/local-run-001/demand/{model.joblib,metrics.json}`
- `joblib` contains `{model, features, target, task, algorithm}`.
- `metrics.json` contains `features` and `model_sha256`.
- `MODEL_PREFIX` is configurable; **verify your actual uploaded prefix**.
- Data lake output is `module.data_lake.bucket_name` and Terraform root has `var.project_name`.

The service accepts a JSON object of **already computed features**. It does not
compute historical demand lags from raw timestamps. In particular, demand lag
features must be computed using observations available at prediction time.
Fare input `trip_distance` means this is an *end-of-trip fare estimate* baseline,
not a pre-trip quote.

## 1. Merge files into your existing repo

Copy `src/`, `deploy/`, `scripts/`, `tests/`, `.github/` and
`infrastructure/modules/serving/` from this overlay. **Do not overwrite** your
existing Terraform root files or `pyproject.toml`.

- Copy `infrastructure/environments-dev-milestone5.tf` to `infrastructure/environments/dev/serving.tf`.
- Append `infrastructure/environments-dev-variables-additions.tf` to your existing `variables.tf`.
- Append `infrastructure/environments-dev-outputs-additions.tf` to your existing `outputs.tf`.
- If `project_name` differs, adjust the `name` argument and workflow ECR repository name.
- If the S3 module output is named differently, adjust `data_bucket`.
- Do not duplicate any existing variable or output declarations.

Merge these dependencies into the existing `[project].dependencies` or
`[project.optional-dependencies].dev` as appropriate: `fastapi>=0.115,<1`,
`uvicorn[standard]>=0.30,<1`, `httpx>=0.27,<1` (test dependency).
`deploy/requirements-serving.txt` defines the container runtime dependencies.
For reproducibility, pin and test exact versions before production use.

## 2. Local test

```bash
source .venv/bin/activate
python -m pip install -e '.[dev]' fastapi 'uvicorn[standard]' httpx
python -m pytest -q tests
python -m ruff check src tests scripts
MODEL_DIR=artifacts/models uvicorn taxi_mlops.serving.app:app --host 127.0.0.1 --port 8080
```

In another terminal:

```bash
curl -fsS http://127.0.0.1:8080/health/ready
curl -fsS http://127.0.0.1:8080/models
```

Use the feature names from `/models` to send predictions. Examples using the
Milestone 4 training feature definitions:

```bash
curl -sS -X POST http://127.0.0.1:8080/predict/fare \
  -H 'Content-Type: application/json' \
  -d '{"features":{"PULocationID":161,"DOLocationID":236,"trip_distance":3.2,"passenger_count":1,"pickup_hour":12,"pickup_dayofweek":2,"pickup_month":1}}'

curl -sS -X POST http://127.0.0.1:8080/predict/demand \
  -H 'Content-Type: application/json' \
  -d '{"features":{"PULocationID":161,"lag_1":30,"lag_24":25,"lag_168":29,"rolling_mean_24":26.1,"rolling_mean_168":28.5,"hour_of_day":12,"day_of_week":2,"month":1}}'
```

Note: the API clips negative predictions to zero; evaluate whether integer
rounding is appropriate downstream for demand counts.

## 3. Verify S3 model artifacts

```bash
export AWS_PROFILE=taxi-dev AWS_DEFAULT_REGION=us-east-1
cd infrastructure/environments/dev
export TAXI_DATA_BUCKET="$(terraform output -raw data_lake_bucket)"
cd ../../..
python scripts/check_model_s3.py --bucket "$TAXI_DATA_BUCKET" --prefix training/local-run-001
```

If your uploaded prefix differs, use that prefix for `MODEL_PREFIX` and
`-var=model_prefix=...`.

## 4. Create ECR first (two-phase bootstrap)

The initial Terraform state must have an ECR repository **before** you can
push a container image. The root variable `enable_api_service` defaults false.

```bash
cd infrastructure/environments/dev
terraform init
terraform validate
terraform plan -target=module.serving.aws_ecr_repository.api -out=ecr.tfplan
terraform apply ecr.tfplan
export REPO="$(terraform output -raw api_ecr_repository_url)"
cd ../../..
```

**Important:** `-target` is only for first-time ECR bootstrap; perform a full
Terraform plan/apply afterward. Terraform output values may be unavailable
until the resource is created and state updated.

## 5. Build and push from Apple Silicon

```bash
aws ecr get-login-password --region us-east-1 | docker login \
  --username AWS --password-stdin "${REPO%/*}"
export TAG="$(git rev-parse HEAD)"
docker build --platform linux/arm64 -f deploy/Dockerfile -t "$REPO:$TAG" .
docker push "$REPO:$TAG"
```

If the image repository already contains the SHA tag, do not repush it: ECR
image tags are immutable. Use a new commit SHA.

## 6. Full Terraform deployment

```bash
cd infrastructure/environments/dev
terraform plan \
  -var="api_image_tag=$TAG" \
  -var="enable_api_service=true" \
  -var="model_prefix=training/local-run-001" \
  -out=serving.tfplan
terraform apply serving.tfplan
terraform output -raw api_url
```

If you deploy manually, **persist the selected tag and service flag** in
`terraform.tfvars` (not tracked), or always pass them to subsequent applies.
Otherwise a later unrelated Terraform apply may disable the service.

```hcl
api_image_tag      = "<deployed-commit-sha>"
enable_api_service = true
model_prefix       = "training/local-run-001"
```

Check:

```bash
URL="$(terraform output -raw api_url)"
curl -fsS "$URL/health/ready"
curl -fsS "$URL/models"
aws ecs describe-services --cluster "$(terraform output -raw api_ecs_cluster_name)" \
  --services "$(terraform output -raw api_ecs_service_name)"
```

For failure diagnosis:

```bash
aws logs tail /ecs/nyc-taxi-mlops-dev-api --follow
```

Common failures: model S3 prefix mismatch; task IAM access denied; incorrect
`metrics.json` checksum; dependency/version mismatch; insufficient Fargate
memory; missing ECR image; or public-subnet egress blocked.

## 7. GitHub Actions

The workflow uses your existing GitHub `dev` environment and expects GitHub
**environment variable** `AWS_TERRAFORM_APPLY_ROLE_ARN` to contain your
existing OIDC-assumable role ARN. If your actual variable name differs,
update the workflow. Its trust policy must permit this repo and `dev`
environment.

The role needs: ECR login/push; Terraform state S3 access; provisioning and
updating VPC, ELBv2, ECS, IAM, CloudWatch Logs, ECR; `iam:PassRole` on the
ECS execution/task roles. Add permissions deliberately to your existing
OIDC apply role; don't create a second GitHub OIDC provider.

GitHub → Actions → `Deploy NYC Taxi API` → Run workflow. The workflow:
1. Tests and lints.
2. Builds a Linux ARM64 container and pushes SHA-tagged image.
3. Applies Terraform with `enable_api_service=true` and the new SHA tag.
4. Waits for ECS service stability and probes `/health/ready`.

**Note:** Existing Terraform workflows must share state-locking/concurrency
rules. If your original workflow auto-applies Terraform, coordinate the
workflows or disable conflicting automatic applies.

## 8. Cost and security

This dev deployment uses two public subnets and `assign_public_ip=true` to
avoid NAT charges. Tasks have a public IP but their inbound security group
allows traffic only from the ALB. ALB is internet-facing on HTTP port 80.
Do not expose sensitive data, use it as an authenticated public API, or call
it production-secure. Before production: add HTTPS/ACM, authentication,
rate limiting/WAF, private subnets + VPC endpoints/NAT, IAM least-privilege
reviews, image pinning/scan gates, alarms, and autoscaling.

The ALB and running Fargate tasks incur hourly charges. Set desired_count=0
for temporary pause (ALB still costs money), or destroy serving infrastructure
when finished. ECR and S3 retained data incur storage charges.

## 9. Evidence

Save screenshots/outputs for tests, `terraform plan`, ECR image digest,
ECS running task, target group healthy state, `/models`, both predictions,
CloudWatch logs, and successful GitHub Actions deployment.
