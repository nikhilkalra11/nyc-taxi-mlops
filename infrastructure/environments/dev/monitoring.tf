module "monitoring" {
  source                  = "../../modules/monitoring"
  name                    = var.project_name
  environment             = "dev"
  region                  = "us-east-1"
  alb_arn_suffix          = module.serving.alb_arn_suffix
  target_group_arn_suffix = module.serving.target_group_arn_suffix
  ecs_cluster_name        = module.serving.ecs_cluster_name
  ecs_service_name        = module.serving.ecs_service_name
  log_group_name          = module.serving.log_group_name
  alert_email             = var.monitoring_alert_email
}