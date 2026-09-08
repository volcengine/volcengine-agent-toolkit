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
  prefix  = "cc-iac-vpcx"
  tags = [
    {
      key   = "purpose"
      value = "terraform-volcenginecc-example"
    }
  ]
}

resource "volcenginecc_vpc_vpc" "main" {
  vpc_name     = "${local.prefix}-vpc"
  description  = "volcenginecc VPC extras example VPC"
  cidr_block   = "10.99.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
  tags         = local.tags
}

resource "volcenginecc_vpc_subnet" "primary" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = "cn-beijing-a"
  subnet_name = "${local.prefix}-subnet-a"
  description = "volcenginecc VPC extras example subnet"
  cidr_block  = "10.99.1.0/24"
  tags        = local.tags
}

resource "volcenginecc_vpc_route_table" "app" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${local.prefix}-rt"
  description      = "volcenginecc VPC extras example route table"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids       = [volcenginecc_vpc_subnet.primary.subnet_id]
  tags             = local.tags
}

resource "volcenginecc_vpc_security_group" "eni" {
  vpc_id              = volcenginecc_vpc_vpc.main.vpc_id
  security_group_name = "${local.prefix}-sg"
  description         = "volcenginecc VPC extras example security group"
  project_name        = local.project
  tags                = local.tags

  ingress_permissions = [
    {
      direction       = "ingress"
      protocol        = "tcp"
      port_start      = 22
      port_end        = 22
      cidr_ip         = "192.0.2.0/24"
      policy          = "accept"
      priority        = 1
      description     = "example ssh ingress"
      prefix_list_id  = ""
      source_group_id = ""
    },
  ]

  egress_permissions = [
    {
      direction       = "egress"
      protocol        = "all"
      port_start      = -1
      port_end        = -1
      cidr_ip         = "0.0.0.0/0"
      policy          = "accept"
      priority        = 1
      description     = "allow all egress"
      prefix_list_id  = ""
      source_group_id = ""
    }
  ]

  depends_on = [
    volcenginecc_vpc_route_table.app,
  ]
}

resource "volcenginecc_vpc_prefix_list" "trusted" {
  prefix_list_name = "${local.prefix}-trusted"
  description      = "volcenginecc VPC extras trusted CIDRs"
  ip_version       = "IPv4"
  max_entries      = 10
  project_name     = local.project
  tags             = local.tags

  prefix_list_entries = [
    {
      cidr        = "192.0.2.0/24"
      description = "TEST-NET-1 example CIDR"
    },
    {
      cidr        = "198.51.100.0/24"
      description = "TEST-NET-2 example CIDR"
    }
  ]
}

resource "volcenginecc_vpc_network_acl" "app" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  network_acl_name = "${local.prefix}-acl"
  description      = "volcenginecc VPC extras subnet ACL"
  project_name     = local.project
  tags             = local.tags

  ingress_acl_entries = [
    {
      cidr_ip                = "10.99.0.0/16"
      description            = "allow internal"
      network_acl_entry_name = "allow-internal"
      policy                 = "accept"
      port                   = "-1/-1"
      protocol               = "all"
    }
  ]

  egress_acl_entries = [
    {
      cidr_ip                = "0.0.0.0/0"
      description            = "allow egress"
      network_acl_entry_name = "allow-egress"
      policy                 = "accept"
      port                   = "-1/-1"
      protocol               = "all"
    }
  ]

  resources = [
    {
      resource_id = volcenginecc_vpc_subnet.primary.subnet_id
    }
  ]

  depends_on = [
    volcenginecc_vpc_route_table.app,
  ]
}

resource "volcenginecc_vpc_eni" "app" {
  network_interface_name             = "${local.prefix}-eni"
  description                        = "volcenginecc VPC extras standalone ENI"
  subnet_id                          = volcenginecc_vpc_subnet.primary.subnet_id
  security_group_ids                 = [volcenginecc_vpc_security_group.eni.security_group_id]
  project_name                       = local.project
  port_security_enabled              = true
  secondary_private_ip_address_count = 1
  tags                               = local.tags
}

resource "volcenginecc_vpc_ha_vip" "app" {
  subnet_id   = volcenginecc_vpc_subnet.primary.subnet_id
  ha_vip_name = "${local.prefix}-havip"
  description = "volcenginecc VPC extras HAVIP"
  ip_address  = "10.99.1.200"
  tags        = local.tags
}

resource "volcenginecc_vpc_bandwidth_package" "shared" {
  bandwidth_package_name = "${local.prefix}-bwp"
  description            = "volcenginecc VPC extras shared bandwidth"
  billing_type           = 2
  bandwidth              = 2
  protocol               = "IPv4"
  isp                    = "BGP"
  project_name           = local.project
  tags                   = local.tags
}

output "prefix_list_id" {
  value = volcenginecc_vpc_prefix_list.trusted.prefix_list_id
}

output "network_acl_id" {
  value = volcenginecc_vpc_network_acl.app.network_acl_id
}

output "network_interface_id" {
  value = volcenginecc_vpc_eni.app.network_interface_id
}

output "ha_vip_id" {
  value = volcenginecc_vpc_ha_vip.app.ha_vip_id
}

output "bandwidth_package_id" {
  value = volcenginecc_vpc_bandwidth_package.shared.bandwidth_package_id
}
