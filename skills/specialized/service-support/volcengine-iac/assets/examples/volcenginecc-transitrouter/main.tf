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
  prefix  = "cc-iac-tr"
}

resource "volcenginecc_transitrouter_transit_router" "main" {
  transit_router_name = "${local.prefix}-router"
  description         = "volcenginecc TransitRouter example"
  asn                 = 64512
  multicast_enabled   = false
  project_name        = local.project
}

output "transit_router_id" {
  value = volcenginecc_transitrouter_transit_router.main.transit_router_id
}
