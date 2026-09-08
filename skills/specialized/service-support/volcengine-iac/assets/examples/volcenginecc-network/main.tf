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
  prefix  = "cc-iac-network"
  tags = [
    {
      key   = "purpose"
      value = "terraform-volcenginecc-example"
    }
  ]
}

resource "volcenginecc_vpc_vpc" "main" {
  vpc_name     = "${local.prefix}-vpc"
  description  = "volcenginecc VPC example"
  cidr_block   = "10.88.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
  tags         = local.tags
}

resource "volcenginecc_vpc_subnet" "primary" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = "cn-beijing-a"
  subnet_name = "${local.prefix}-subnet-a"
  description = "volcenginecc subnet example a"
  cidr_block  = "10.88.1.0/24"
  tags        = local.tags
}

resource "volcenginecc_vpc_subnet" "secondary" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = "cn-beijing-b"
  subnet_name = "${local.prefix}-subnet-b"
  description = "volcenginecc subnet example b"
  cidr_block  = "10.88.2.0/24"
  tags        = local.tags
}

resource "volcenginecc_vpc_route_table" "app" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${local.prefix}-rt"
  description      = "volcenginecc route table example"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids = [
    volcenginecc_vpc_subnet.primary.subnet_id,
    volcenginecc_vpc_subnet.secondary.subnet_id,
  ]
  tags = local.tags
}

resource "volcenginecc_vpc_security_group" "app" {
  vpc_id              = volcenginecc_vpc_vpc.main.vpc_id
  security_group_name = "${local.prefix}-sg"
  description         = "volcenginecc security group example"
  project_name        = local.project

  ingress_permissions = [
    {
      description     = "allow-http"
      direction       = "ingress"
      policy          = "accept"
      priority        = 1
      protocol        = "tcp"
      port_start      = 80
      port_end        = 80
      cidr_ip         = "0.0.0.0/0"
      prefix_list_id  = ""
      source_group_id = ""
    }
  ]

  egress_permissions = [
    {
      description     = "allow-all-egress"
      direction       = "egress"
      policy          = "accept"
      priority        = 1
      protocol        = "all"
      port_start      = -1
      port_end        = -1
      cidr_ip         = "0.0.0.0/0"
      prefix_list_id  = ""
      source_group_id = ""
    }
  ]

  tags = local.tags

  depends_on = [
    volcenginecc_vpc_route_table.app,
  ]
}

resource "volcenginecc_vpc_eip" "standalone" {
  name         = "${local.prefix}-eip"
  description  = "volcenginecc standalone EIP example"
  isp          = "BGP"
  billing_type = 2
  bandwidth    = 1
  project_name = local.project
  tags         = local.tags
}

resource "volcenginecc_natgateway_ngw" "public" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  subnet_id        = volcenginecc_vpc_subnet.primary.subnet_id
  nat_gateway_name = "${local.prefix}-nat"
  description      = "volcenginecc public NAT gateway example"
  spec             = "Small"
  billing_type     = 2
  network_type     = "internet"
  project_name     = local.project
  tags             = local.tags

  depends_on = [
    volcenginecc_vpc_route_table.app,
  ]
}

resource "volcenginecc_vpc_eip" "nat" {
  name          = "${local.prefix}-nat-eip"
  description   = "volcenginecc NAT EIP example"
  isp           = "BGP"
  billing_type  = 2
  bandwidth     = 1
  project_name  = local.project
  instance_id   = volcenginecc_natgateway_ngw.public.nat_gateway_id
  instance_type = "Nat"
  tags          = local.tags
}

resource "volcenginecc_natgateway_snatentry" "subnet_primary" {
  nat_gateway_id  = volcenginecc_natgateway_ngw.public.nat_gateway_id
  eip_id          = volcenginecc_vpc_eip.nat.allocation_id
  snat_entry_name = "${local.prefix}-snat-a"
  subnet_id       = volcenginecc_vpc_subnet.primary.subnet_id
}

resource "volcenginecc_natgateway_dnatentry" "http_test" {
  nat_gateway_id  = volcenginecc_natgateway_ngw.public.nat_gateway_id
  dnat_entry_name = "${local.prefix}-dnat-http"
  external_ip     = volcenginecc_vpc_eip.nat.eip_address
  external_port   = "8080"
  internal_ip     = "10.88.1.10"
  internal_port   = "80"
  port_type       = "specified"
  protocol        = "tcp"
}

output "vpc_id" {
  value = volcenginecc_vpc_vpc.main.vpc_id
}

output "subnet_ids" {
  value = [
    volcenginecc_vpc_subnet.primary.subnet_id,
    volcenginecc_vpc_subnet.secondary.subnet_id,
  ]
}

output "security_group_id" {
  value = volcenginecc_vpc_security_group.app.security_group_id
}

output "route_table_id" {
  value = volcenginecc_vpc_route_table.app.route_table_id
}

output "eip_id" {
  value = volcenginecc_vpc_eip.standalone.allocation_id
}

output "nat_gateway_id" {
  value = volcenginecc_natgateway_ngw.public.nat_gateway_id
}

output "snat_entry_id" {
  value = volcenginecc_natgateway_snatentry.subnet_primary.snat_entry_id
}

output "dnat_entry_id" {
  value = volcenginecc_natgateway_dnatentry.http_test.dnat_entry_id
}
