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
}

resource "volcenginecc_clb_acl" "main" {
  acl_name     = "cc-iac-clb-acl"
  description  = "volcenginecc CLB ACL example"
  project_name = local.project

  acl_entries = [
    {
      description = "example entry"
      entry       = "198.51.100.11/32"
    }
  ]
}

output "acl_id" {
  value = volcenginecc_clb_acl.main.acl_id
}
