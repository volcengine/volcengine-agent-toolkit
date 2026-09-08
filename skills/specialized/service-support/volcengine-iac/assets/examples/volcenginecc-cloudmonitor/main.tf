terraform {
  required_version = ">= 1.0.7"

  required_providers {
    volcenginecc = {
      source  = "volcengine/volcenginecc"
      version = "~> 0.0.46"
    }
  }
}

provider "volcenginecc" {}

resource "volcenginecc_cloudmonitor_rule" "ecs_cpu" {
  rule_name        = "cc-iac-cm-ecs-cpu"
  description      = "volcenginecc CloudMonitor example disabled ECS CPU rule"
  rule_type        = "static"
  namespace        = "VCM_ECS"
  sub_namespace    = "Instance"
  level            = "warning"
  evaluation_count = 1
  enable_state     = "disable"
  regions          = ["cn-beijing"]
  project_name     = "default"

  original_dimensions = {
    key    = "ResourceID"
    values = ["*"]
  }

  multiple_conditions = false
  condition_operator  = "&&"

  conditions = [
    {
      metric_name         = "CpuTotal"
      statistics          = "avg"
      comparison_operator = ">"
      threshold           = "95"
      period              = "60"
      metric_unit         = "Percent"
    }
  ]

  no_data = {
    enable           = false
    evaluation_count = 3
  }

  recovery_notify = {
    enable = false
  }

  silence_time    = 5
  alert_methods   = ["Webhook"]
  webhook         = "https://example.com/volcenginecc-cloudmonitor-disabled"
  effect_start_at = "00:00"
  effect_end_at   = "23:59"
}

output "rule_id" {
  value = volcenginecc_cloudmonitor_rule.ecs_cpu.rule_id
}
