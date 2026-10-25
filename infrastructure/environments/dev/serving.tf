module "serving" {
  source = "../../modules/serving"

  # Project identification
  name        = var.project_name
  environment = "dev"
  region      = "us-east-1"

  # Existing Milestone 3 S3 data lake
  data_bucket = module.data_lake.bucket_name

  # Milestone 4 trained model artifacts
  model_prefix = var.model_prefix

  # Milestone 5 container configuration
  image_tag      = var.api_image_tag
  enable_service = var.enable_api_service

  # ECS Fargate configuration
  container_port = 8080
  cpu            = 1024
  memory         = 2048
  desired_count  = 1
}