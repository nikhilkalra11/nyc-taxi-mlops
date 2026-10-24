data "aws_caller_identity" "current" {}
module "data_lake" {
  source      = "../../modules/s3"
  bucket_name = "${var.project_name}-data-dev-${data.aws_caller_identity.current.account_id}-us-east-1"
  environment = "dev"
}
output "aws_account_id" { value = data.aws_caller_identity.current.account_id }
output "aws_region" { value = "us-east-1" }
