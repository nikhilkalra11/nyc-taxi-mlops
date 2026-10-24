output "data_lake_bucket" { value = module.data_lake.bucket_name }
output "api_ecr_repository_url" { value = module.serving.ecr_repository_url }
output "api_ecr_repository_name" { value = module.serving.ecr_repository_name }
output "api_url" { value = module.serving.api_url }
output "api_ecs_cluster_name" { value = module.serving.ecs_cluster_name }
output "api_ecs_service_name" { value = module.serving.ecs_service_name }