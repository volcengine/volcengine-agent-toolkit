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
  tags = [
    {
      key   = "purpose"
      value = "terraform-volcenginecc-example"
    }
  ]
}

variable "zone_name" {
  description = "A unique apex domain for Cloud DNS verification. Use a domain you own for real traffic."
  type        = string
  default     = "cc-iac-dns-0530043107.com"
}

resource "volcenginecc_dns_zone" "main" {
  zone_name    = var.zone_name
  remark       = "volcenginecc DNS example"
  project_name = local.project
  tags         = local.tags
}

output "zone_id" {
  value = volcenginecc_dns_zone.main.zid
}

output "allocated_dns_servers" {
  value = volcenginecc_dns_zone.main.allocate_dns_server_list
}
