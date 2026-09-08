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
  prefix  = "cc-iac-clb"
  zone_a  = "cn-beijing-a"
  zone_b  = "cn-beijing-b"
  tags = [
    {
      key   = "purpose"
      value = "terraform-volcenginecc-example"
    }
  ]
}

resource "volcenginecc_vpc_vpc" "main" {
  vpc_name     = "${local.prefix}-vpc"
  description  = "volcenginecc CLB example VPC"
  cidr_block   = "10.91.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
  tags         = local.tags
}

resource "volcenginecc_vpc_subnet" "primary" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = local.zone_a
  subnet_name = "${local.prefix}-subnet"
  description = "volcenginecc CLB example subnet"
  cidr_block  = "10.91.1.0/24"
  tags        = local.tags
}

resource "volcenginecc_vpc_route_table" "app" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${local.prefix}-rt"
  description      = "volcenginecc CLB example route table"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids       = [volcenginecc_vpc_subnet.primary.subnet_id]
  tags             = local.tags
}

resource "volcenginecc_clb_clb" "main" {
  load_balancer_name            = "${local.prefix}-clb"
  load_balancer_spec            = "small_1"
  address_ip_version            = "ipv4"
  bypass_security_group_enabled = "off"
  description                   = "volcenginecc CLB example"
  load_balancer_billing_type    = 2
  master_zone_id                = local.zone_a
  slave_zone_id                 = local.zone_b
  project_name                  = local.project
  subnet_id                     = volcenginecc_vpc_subnet.primary.subnet_id
  type                          = "private"
  vpc_id                        = volcenginecc_vpc_vpc.main.vpc_id
  tags                          = local.tags

  depends_on = [
    volcenginecc_vpc_route_table.app,
  ]
}

output "load_balancer_id" {
  value = volcenginecc_clb_clb.main.load_balancer_id
}

output "vpc_id" {
  value = volcenginecc_vpc_vpc.main.vpc_id
}

output "subnet_id" {
  value = volcenginecc_vpc_subnet.primary.subnet_id
}
