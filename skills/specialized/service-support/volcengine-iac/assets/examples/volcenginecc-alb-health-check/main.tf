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

locals {
  project = "default"
  prefix  = "cc-iac-alb"
  tags = [
    {
      key   = "purpose"
      value = "terraform-volcenginecc-example"
    }
  ]
}

resource "volcenginecc_alb_health_check_template" "http" {
  health_check_template_name = "${local.prefix}-hc"
  description                = "volcenginecc ALB health check template example"
  health_check_domain        = "example.com"
  health_check_http_code     = "http_2xx,http_3xx"
  health_check_http_version  = "HTTP1.1"
  health_check_interval      = 2
  health_check_method        = "GET"
  health_check_port          = 0
  health_check_protocol      = "HTTP"
  health_check_timeout       = 2
  health_check_uri           = "/"
  healthy_threshold          = 3
  unhealthy_threshold        = 3
  project_name               = local.project
  tags                       = local.tags
}

output "health_check_template_id" {
  value = volcenginecc_alb_health_check_template.http.health_check_template_id
}
