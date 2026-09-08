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
  prefix  = "cc-iac-tmt"
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
  description  = "volcenginecc traffic mirror target example VPC"
  cidr_block   = "10.111.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
  tags         = local.tags
}

resource "volcenginecc_vpc_subnet" "primary" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = local.zone_a
  subnet_name = "${local.prefix}-subnet"
  description = "volcenginecc traffic mirror target example subnet"
  cidr_block  = "10.111.1.0/24"
  tags        = local.tags
}

resource "volcenginecc_vpc_route_table" "app" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${local.prefix}-rt"
  description      = "volcenginecc traffic mirror target example route table"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids       = [volcenginecc_vpc_subnet.primary.subnet_id]
  tags             = local.tags
}

resource "volcenginecc_clb_clb" "target" {
  load_balancer_name            = "${local.prefix}-clb"
  load_balancer_spec            = "small_1"
  address_ip_version            = "ipv4"
  bypass_security_group_enabled = "off"
  description                   = "volcenginecc traffic mirror target CLB"
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

resource "volcenginecc_vpc_traffic_mirror_target" "clb" {
  traffic_mirror_target_name = "${local.prefix}-target"
  description                = "volcenginecc traffic mirror target example"
  instance_id                = volcenginecc_clb_clb.target.load_balancer_id
  instance_type              = "ClbInstance"
  project_name               = local.project
  tags                       = local.tags
}

output "traffic_mirror_target_id" {
  value = volcenginecc_vpc_traffic_mirror_target.clb.traffic_mirror_target_id
}

output "load_balancer_id" {
  value = volcenginecc_clb_clb.target.load_balancer_id
}
