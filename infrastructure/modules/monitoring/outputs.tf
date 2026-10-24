output "sns_topic_arn" { value = aws_sns_topic.alerts.arn }
output "dashboard_name" { value = aws_cloudwatch_dashboard.serving.dashboard_name }
output "alarm_names" {
  value = [
    aws_cloudwatch_metric_alarm.alb_5xx.alarm_name,
    aws_cloudwatch_metric_alarm.target_5xx.alarm_name,
    aws_cloudwatch_metric_alarm.latency.alarm_name,
    aws_cloudwatch_metric_alarm.unhealthy.alarm_name,
    aws_cloudwatch_metric_alarm.cpu.alarm_name,
    aws_cloudwatch_metric_alarm.memory.alarm_name,
    aws_cloudwatch_metric_alarm.no_running_tasks.alarm_name
  ]
}
