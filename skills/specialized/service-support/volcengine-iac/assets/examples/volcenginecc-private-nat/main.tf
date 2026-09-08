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
  prefix  = "cc-iac-pnat"
  zone_id = "cn-beijing-a"
  tags = [
    {
      key   = "purpose"
      value = "terraform-volcenginecc-example"
    }
  ]
}

resource "volcenginecc_vpc_vpc" "main" {
  vpc_name     = "${local.prefix}-vpc"
  description  = "volcenginecc private NAT example VPC"
  cidr_block   = "10.95.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
  tags         = local.tags
}

resource "volcenginecc_vpc_subnet" "primary" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = local.zone_id
  subnet_name = "${local.prefix}-subnet-a"
  description = "volcenginecc private NAT example subnet"
  cidr_block  = "10.95.1.0/24"
  tags        = local.tags
}

resource "volcenginecc_vpc_route_table" "app" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${local.prefix}-rt"
  description      = "volcenginecc private NAT example route table"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids       = [volcenginecc_vpc_subnet.primary.subnet_id]
  tags             = local.tags
}

resource "volcenginecc_natgateway_ngw" "private" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  subnet_id        = volcenginecc_vpc_subnet.primary.subnet_id
  nat_gateway_name = "${local.prefix}-nat"
  description      = "volcenginecc private NAT gateway example"
  billing_type     = 3
  network_type     = "intranet"
  project_name     = local.project
  tags             = local.tags

  depends_on = [
    volcenginecc_vpc_route_table.app,
  ]
}

resource "volcenginecc_natgateway_nat_ip" "main" {
  nat_gateway_id     = volcenginecc_natgateway_ngw.private.nat_gateway_id
  nat_ip_name        = "${local.prefix}-nat-ip"
  nat_ip_description = "volcenginecc private NAT transit IP example"
}

output "nat_gateway_id" {
  value = volcenginecc_natgateway_ngw.private.nat_gateway_id
}

output "nat_ip_id" {
  value = volcenginecc_natgateway_nat_ip.main.nat_ip_id
}
