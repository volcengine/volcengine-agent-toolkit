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
  prefix  = "cc-iac-efs"
  zone    = "cn-beijing-a"
}

resource "volcenginecc_efs_file_system" "main" {
  file_system_name    = "${local.prefix}-fs"
  description         = "volcenginecc EFS example file system"
  charge_type         = "PayAsYouGo"
  zone_id             = local.zone
  instance_type       = "Premium"
  performance_density = "Premium_125"
  project_name        = local.project

  performance = {
    bandwidth_mode        = "Provisioned"
    provisioned_bandwidth = 300
  }
}

output "file_system_id" {
  value = volcenginecc_efs_file_system.main.file_system_id
}
