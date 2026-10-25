# NYC Taxi MLOps — Capstone Overview

## Project Objective

The objective of this capstone is to design and build an end-to-end MLOps platform that combines machine learning development with cloud infrastructure, CI/CD automation, model lifecycle management, and observability.

The platform uses NYC Yellow Taxi data to solve two regression problems: fare prediction and demand prediction.

## Problem Statement

Machine learning projects often focus on model development but overlook the operational requirements of managing models in real environments.

These requirements include reproducible training, version control, model evaluation, deployment, monitoring, and secure infrastructure access.

This project addresses those challenges through an AWS-based MLOps architecture.

## Solution Overview

The platform implements a workflow for:

- Ingesting and preparing taxi trip data.
- Engineering features for two prediction tasks.
- Training and evaluating machine learning models.
- Tracking experiments with MLflow.
- Registering model artifacts in S3.
- Comparing candidates with incumbent models.
- Approving model promotions.
- Preparing automated ECS deployments.
- Monitoring inference infrastructure and feature drift.

The complete architectural design also incorporates deployment health verification, rollback, and scheduled retraining.

## Capstone Milestones

| Milestone | Description |
|---|---|
| 0–1 | Project setup, AWS infrastructure, Terraform, and GitHub OIDC |
| 2–3 | Data ingestion, validation, cleaning, and feature engineering |
| 4 | Model training, evaluation, and MLflow tracking |
| 5 | FastAPI model serving, Docker, ECR, and ECS Fargate |
| 6 | Monitoring, CloudWatch alarms, and offline drift detection |
| 7 | Model registry, candidate evaluation, approval, and deployment workflow preparation |
| 8 | Architecture documentation and capstone demonstration |

## Capstone Demonstration

### Demonstration 1 — Infrastructure

Explain how Terraform provisions AWS resources and how IAM and GitHub OIDC secure automated workflows.

### Demonstration 2 — Data Pipeline

Show the S3 data layout and explain how raw taxi records are transformed into fare and demand feature datasets.

### Demonstration 3 — Model Training

Explain how LightGBM and XGBoost are trained and compared, and how MLflow records experiment information.

### Demonstration 4 — Model Lifecycle

Walk through candidate registration, evaluation reports, and approval records stored in S3.

Explain how the deployment workflow is designed to promote an approved model to ECS.

### Demonstration 5 — Model Serving

Present the FastAPI prediction endpoints and explain the Docker, ECR, ECS Fargate, and Application Load Balancer architecture.

### Demonstration 6 — Monitoring

Show the CloudWatch monitoring configuration and explain how PSI drift reports are used to analyze feature distribution changes.

## Key Engineering Learnings

The project demonstrates practical experience in:

- AWS infrastructure design.
- Infrastructure as Code.
- CI/CD and workflow automation.
- Machine learning model training and evaluation.
- MLflow experiment tracking.
- Containerized model serving.
- Model lifecycle and approval controls.
- IAM and OIDC authentication.
- Monitoring and observability.
- Reliability-oriented deployment architecture.

## Project Status

The capstone includes the core data, training, serving, monitoring, model registration, evaluation, and approval components.

The automated deployment workflow was prepared as an extension of the model lifecycle. Live ECS model rollout, automatic rollback validation, and operational scheduled retraining were not completed as part of the final validation.

## Conclusion

NYC Taxi MLOps demonstrates how cloud engineering, DevOps automation, and machine learning practices can be integrated into a unified platform.

The project provides a practical foundation for managing the complete machine learning lifecycle on AWS, with additional deployment reliability and continuous training capabilities identified for future production hardening.