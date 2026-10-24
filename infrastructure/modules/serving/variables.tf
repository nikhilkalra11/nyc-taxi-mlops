variable "name" { type = string }
variable "environment" { type = string }
variable "region" { type = string }
variable "data_bucket" { type = string }
variable "model_prefix" { type = string }
variable "image_tag" { type = string }
variable "container_port" {
  type    = number
  default = 8080
}
variable "cpu" {
  type    = number
  default = 1024
}
variable "memory" {
  type    = number
  default = 2048
}
variable "desired_count" {
  type    = number
  default = 1
}
variable "enable_service" {
  type    = bool
  default = true
}
