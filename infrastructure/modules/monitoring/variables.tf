variable "name" { type = string }
variable "environment" { type = string }
variable "region" { type = string }
variable "alb_arn_suffix" { type = string }
variable "target_group_arn_suffix" { type = string }
variable "ecs_cluster_name" { type = string }
variable "ecs_service_name" { type = string }
variable "log_group_name" { type = string }
variable "alert_email" {
  description = "Optional email endpoint; recipient must confirm SNS subscription."
  type        = string
  default     = ""
}
variable "evaluation_periods" {
  type    = number
  default = 2
}
variable "period_seconds" {
  type    = number
  default = 60
}
variable "alb_5xx_threshold" {
  type    = number
  default = 5
}
variable "latency_threshold_seconds" {
  type    = number
  default = 2
}
variable "cpu_threshold_percent" {
  type    = number
  default = 80
}
variable "memory_threshold_percent" {
  type    = number
  default = 85
}
