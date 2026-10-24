variable "github_owner" {
  description = "GitHub repository owner"
  type        = string
}

variable "github_owner_id" {
  description = "Permanent GitHub owner ID"
  type        = string
}

variable "github_repository" {
  description = "GitHub repository name"
  type        = string
  default     = "nyc-taxi-mlops"
}

variable "github_repository_id" {
  description = "Permanent GitHub repository ID"
  type        = string
}

variable "environment" {
  description = "Protected GitHub deployment environment"
  type        = string
  default     = "dev"
}