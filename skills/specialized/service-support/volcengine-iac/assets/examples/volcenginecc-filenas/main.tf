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
  prefix  = "cc-iac-filenas"
  zone    = "cn-beijing-a"
}

resource "volcenginecc_filenas_instance" "main" {
  file_system_name = "${local.prefix}-fs"
  description      = "volcenginecc FileNAS example file system"
  charge_type      = "PayAsYouGo"
  file_system_type = "Extreme"
  protocol_type    = "NFS"
  storage_type     = "Standard"
  zone_id          = local.zone
  project_name     = local.project

  capacity = {
    total = 105
  }
}

output "file_system_id" {
  value = volcenginecc_filenas_instance.main.file_system_id
}
