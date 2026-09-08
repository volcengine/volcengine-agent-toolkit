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
  prefix  = "cc-iac-tmf"
  tags = [
    {
      key   = "env"
      value = "test"
    }
  ]
}

resource "volcenginecc_vpc_traffic_mirror_filter" "app" {
  traffic_mirror_filter_name = local.prefix
  description                = "volcenginecc traffic mirror filter example"
  project_name               = local.project
  tags                       = local.tags
}

resource "volcenginecc_vpc_traffic_mirror_filter_rule" "ingress_http" {
  traffic_mirror_filter_id = volcenginecc_vpc_traffic_mirror_filter.app.traffic_mirror_filter_id
  traffic_direction        = "ingress"
  priority                 = 100
  policy                   = "accept"
  protocol                 = "tcp"
  source_cidr_block        = "10.0.0.0/8"
  source_port_range        = "1/65535"
  destination_cidr_block   = "10.0.0.0/8"
  destination_port_range   = "80/80"
  description              = "Mirror inbound HTTP traffic inside private CIDRs"
}

output "traffic_mirror_filter_id" {
  value = volcenginecc_vpc_traffic_mirror_filter.app.traffic_mirror_filter_id
}

output "traffic_mirror_filter_rule_id" {
  value = volcenginecc_vpc_traffic_mirror_filter_rule.ingress_http.traffic_mirror_filter_rule_id
}
