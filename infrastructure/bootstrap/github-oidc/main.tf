data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id

  state_bucket = "nyc-taxi-mlops-tfstate-${local.account_id}"

  github_repo_identity = (
    "${var.github_owner}@${var.github_owner_id}/${var.github_repository}@${var.github_repository_id}"
  )

  github_dev_subject = (
    "repo:${local.github_repo_identity}:environment:${var.environment}"
  )

  github_main_subject = (
    "repo:${local.github_repo_identity}:ref:refs/heads/main"
  )
}

resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = [
    "sts.amazonaws.com"
  ]
}