variable "project_name" {
  type    = string
  default = "nyc-taxi-mlops"
}

variable "model_prefix" {
  type    = string
  default = "training/local-run-001"
}
variable "api_image_tag" {
  type    = string
  default = "bootstrap"
}
variable "enable_api_service" {
  type    = bool
  default = false
}

variable "monitoring_alert_email" {
  description = "Optional email to subscribe to monitoring alarms; confirm SNS email to activate."
  type        = string
  default     = ""
}

