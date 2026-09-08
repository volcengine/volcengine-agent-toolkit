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

resource "volcenginecc_alb_customized_cfg" "main" {
  customized_cfg_name    = "cc-iac-alb-cfg"
  description            = "volcenginecc ALB customized config example"
  project_name           = "default"
  customized_cfg_content = "client_max_body_size 60M;\r\nkeepalive_timeout 77s;\r\n"
}

output "customized_cfg_id" {
  value = volcenginecc_alb_customized_cfg.main.customized_cfg_id
}
