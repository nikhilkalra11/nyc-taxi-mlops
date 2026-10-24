provider "aws" {
  region = "us-east-1"

  default_tags {
    tags = {
      Project   = "nyc-taxi-mlops"
      ManagedBy = "terraform"
      Component = "github-oidc"
    }
  }
}