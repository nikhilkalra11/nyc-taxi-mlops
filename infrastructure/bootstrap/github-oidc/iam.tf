data "aws_iam_policy_document" "plan_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type = "Federated"
      identifiers = [
        aws_iam_openid_connect_provider.github.arn
      ]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [local.github_main_subject]
    }
  }
}

data "aws_iam_policy_document" "apply_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type = "Federated"
      identifiers = [
        aws_iam_openid_connect_provider.github.arn
      ]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [local.github_dev_subject]
    }
  }
}

resource "aws_iam_role" "terraform_plan" {
  name               = "nyc-taxi-terraform-plan"
  assume_role_policy = data.aws_iam_policy_document.plan_trust.json
}

resource "aws_iam_role" "terraform_apply" {
  name               = "nyc-taxi-terraform-apply"
  assume_role_policy = data.aws_iam_policy_document.apply_trust.json
}

data "aws_iam_policy_document" "state_plan" {
  statement {
    sid       = "ListStateBucket"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${local.state_bucket}"]
  }

  statement {
    sid = "ReadState"

    actions = ["s3:GetObject"]

    resources = [
      "arn:aws:s3:::${local.state_bucket}/dev/terraform.tfstate"
    ]
  }

  statement {
    sid = "ManageStateLock"

    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject"
    ]

    resources = [
      "arn:aws:s3:::${local.state_bucket}/dev/terraform.tfstate.tflock"
    ]
  }
}

data "aws_iam_policy_document" "state_apply" {
  statement {
    sid       = "ListStateBucket"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${local.state_bucket}"]
  }

  statement {
    sid = "ReadWriteState"

    actions = [
      "s3:GetObject",
      "s3:PutObject"
    ]

    resources = [
      "arn:aws:s3:::${local.state_bucket}/dev/terraform.tfstate"
    ]
  }

  statement {
    sid = "ManageStateLock"

    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject"
    ]

    resources = [
      "arn:aws:s3:::${local.state_bucket}/dev/terraform.tfstate.tflock"
    ]
  }
}

resource "aws_iam_role_policy" "plan_state" {
  name   = "terraform-state-read"
  role   = aws_iam_role.terraform_plan.id
  policy = data.aws_iam_policy_document.state_plan.json
}

resource "aws_iam_role_policy" "apply_state" {
  name   = "terraform-state-write"
  role   = aws_iam_role.terraform_apply.id
  policy = data.aws_iam_policy_document.state_apply.json
}

data "aws_iam_policy_document" "terraform_discovery" {
  statement {
    actions = [
      "sts:GetCallerIdentity",
      "ec2:Describe*",
      "s3:ListAllMyBuckets",
      "s3:GetBucketLocation"
    ]

    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "plan_discovery" {
  name   = "terraform-discovery"
  role   = aws_iam_role.terraform_plan.id
  policy = data.aws_iam_policy_document.terraform_discovery.json
}

resource "aws_iam_role_policy" "apply_discovery" {
  name   = "terraform-discovery"
  role   = aws_iam_role.terraform_apply.id
  policy = data.aws_iam_policy_document.terraform_discovery.json
}

data "aws_iam_policy_document" "data_lake_management" {
  statement {
    sid = "ManageDataLakeBucket"

    actions = [
      "s3:CreateBucket",
      "s3:DeleteBucket",
      "s3:ListBucket",
      "s3:GetBucketLocation",
      "s3:GetBucketVersioning",
      "s3:PutBucketVersioning",
      "s3:GetEncryptionConfiguration",
      "s3:PutEncryptionConfiguration",
      "s3:GetBucketPublicAccessBlock",
      "s3:PutBucketPublicAccessBlock",
      "s3:GetBucketOwnershipControls",
      "s3:PutBucketOwnershipControls",
      "s3:GetBucketPolicy",
      "s3:PutBucketPolicy",
      "s3:DeleteBucketPolicy",
      "s3:GetBucketTagging",
      "s3:PutBucketTagging",
      "s3:ListBucketVersions"
    ]

    resources = [
      "arn:aws:s3:::nyc-taxi-mlops-data-dev-${data.aws_caller_identity.current.account_id}-us-east-1"
    ]
  }
}

resource "aws_iam_role_policy" "apply_data_lake" {
  name   = "terraform-data-lake-management"
  role   = aws_iam_role.terraform_apply.id
  policy = data.aws_iam_policy_document.data_lake_management.json
}