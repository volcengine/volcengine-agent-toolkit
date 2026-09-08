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
  prefix  = "cc-iac-dc"
}

resource "volcenginecc_directconnect_direct_connect_gateway" "main" {
  direct_connect_gateway_name = "${local.prefix}-gw"
  description                 = "volcenginecc DirectConnect example gateway"
  enable_ipv_6                = false
  project_name                = local.project
}

output "direct_connect_gateway_id" {
  value = volcenginecc_directconnect_direct_connect_gateway.main.direct_connect_gateway_id
}
