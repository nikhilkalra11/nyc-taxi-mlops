# NYC Taxi MLOps — System Architecture

## Overview

The NYC Taxi MLOps platform is designed as a modular, cloud-native machine learning system deployed on AWS.

The architecture separates data processing, model training, model lifecycle management, inference serving, and monitoring to support maintainability and reproducibility.

## Architecture Layers

### 1. Infrastructure Layer

Terraform provisions and manages the cloud infrastructure.

Major AWS services include:

- Amazon S3 for datasets, features, models, and reports.
- Amazon ECR for container images.
- Amazon ECS Fargate for inference workloads.
- Application Load Balancer for API access.
- AWS IAM for access management.
- CloudWatch for logging, metrics, and alarms.
- SNS for notifications.

### 2. Data Engineering Layer

The data pipeline ingests NYC Yellow Taxi records, validates and cleans the dataset, and generates features for the two prediction tasks.

Processed features are stored in Amazon S3 using separate fare and demand datasets.

Chronological splitting helps reduce temporal leakage during model development.

### 3. Model Training Layer

The training pipeline uses LightGBM and XGBoost to train competing regression models.

Model selection is based on validation RMSE.

MLflow records experiment information, while selected model artifacts and evaluation metrics are persisted to S3.

### 4. Model Lifecycle Layer

The model lifecycle manages the transition from a trained candidate to an approved model version.

The workflow includes:

1. Model candidate creation.
2. Model registration.
3. Candidate evaluation against the incumbent.
4. Evaluation-based eligibility checks.
5. Manual approval.
6. Automated deployment workflow.
7. Deployment verification and recovery design.

The first five stages form the implemented model promotion workflow. The deployment workflow was prepared separately, while live rollout and rollback verification remain outstanding.

### 5. Inference Layer

FastAPI provides REST endpoints for fare and demand predictions.

The application is packaged into a Docker container, published to ECR, and served using ECS Fargate.

The Application Load Balancer forwards prediction requests to the running application.

Model artifacts are retrieved from S3 during application initialization.

### 6. Monitoring Layer

CloudWatch provides operational observability through application logs, metrics, and alarms.

SNS is used for alarm notifications.

Offline Population Stability Index analysis supports detection of changes in feature distributions.

## CI/CD Architecture

GitHub Actions coordinates the model lifecycle workflows.

AWS authentication uses GitHub OIDC and dedicated IAM roles, avoiding static cloud credentials.

The workflow architecture separates model training, model evaluation, approval, and deployment responsibilities.

## Architecture Design Decisions

| Component | Design Rationale |
|---|---|
| Terraform | Reproducible, version-controlled infrastructure |
| Amazon S3 | Durable storage for datasets and model artifacts |
| MLflow | Experiment tracking and model comparison |
| GitHub Actions | Automated ML and deployment workflows |
| Amazon ECR | Centralized Docker image storage |
| ECS Fargate | Container orchestration without managing servers |
| FastAPI | Lightweight Python-based inference API |
| CloudWatch | Native AWS monitoring and alerting |
| GitHub OIDC | Short-lived credentials and secure AWS authentication |

## Reliability and Recovery

The architecture is designed to support controlled model promotion.

Approval-based deployment reduces the risk of unreviewed models reaching production.

The deployment design supports creating a new ECS task definition revision using an approved model artifact prefix.

Health verification and automatic rollback are identified as recovery mechanisms for the extended deployment lifecycle. Their live execution and effectiveness require validation before production use.

## Summary

The architecture demonstrates how AWS infrastructure, DevOps automation, and machine learning workflows can be combined to create a modular MLOps platform.

Its major design principles are reproducibility, separation of responsibilities, model traceability, infrastructure automation, and operational visibility.