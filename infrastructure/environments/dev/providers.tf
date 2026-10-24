provider "aws" {
  region = "us-east-1"

  default_tags {
    tags = {
      Project     = "nyc-taxi-mlops"
      Environment = "dev"
      ManagedBy   = "terraform"
    }
  }
}