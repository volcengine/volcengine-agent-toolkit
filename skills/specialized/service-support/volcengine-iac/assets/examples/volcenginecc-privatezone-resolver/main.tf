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
  prefix  = "cc-iac-pzone"
}

resource "volcenginecc_vpc_vpc" "main" {
  vpc_name     = "${local.prefix}-vpc"
  description  = "volcenginecc PrivateZone resolver example VPC"
  cidr_block   = "10.89.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
}

resource "volcenginecc_vpc_subnet" "a" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = "cn-beijing-a"
  subnet_name = "${local.prefix}-subnet-a"
  cidr_block  = "10.89.1.0/24"
}

resource "volcenginecc_vpc_subnet" "b" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = "cn-beijing-b"
  subnet_name = "${local.prefix}-subnet-b"
  cidr_block  = "10.89.2.0/24"
}

resource "volcenginecc_vpc_route_table" "app" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${local.prefix}-rt"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids       = [volcenginecc_vpc_subnet.a.subnet_id, volcenginecc_vpc_subnet.b.subnet_id]
}

resource "volcenginecc_privatezone_resolver_endpoint" "outbound" {
  name          = "${local.prefix}-endpoint"
  vpc_id        = volcenginecc_vpc_vpc.main.vpc_id
  vpc_region    = "cn-beijing"
  direction     = "OUTBOUND"
  endpoint_type = "IPv4"
  project_name  = local.project

  ip_configs = [
    { az_id = "cn-beijing-a", subnet_id = volcenginecc_vpc_subnet.a.subnet_id, ip = "10.89.1.44" },
    { az_id = "cn-beijing-b", subnet_id = volcenginecc_vpc_subnet.b.subnet_id, ip = "10.89.2.44" }
  ]

  depends_on = [volcenginecc_vpc_route_table.app]
}

resource "volcenginecc_privatezone_resolver_rule" "outbound" {
  name        = "${local.prefix}-rule"
  type        = "OUTBOUND"
  endpoint_id = tonumber(volcenginecc_privatezone_resolver_endpoint.outbound.endpoint_id)
  zone_name   = "corp.internal"

  forward_i_ps = [
    { ip = "10.89.250.10", port = 53 }
  ]

  vp_cs = [
    { region = "cn-beijing", vpc_id = volcenginecc_vpc_vpc.main.vpc_id }
  ]
}

output "endpoint_id" {
  value = volcenginecc_privatezone_resolver_endpoint.outbound.endpoint_id
}
