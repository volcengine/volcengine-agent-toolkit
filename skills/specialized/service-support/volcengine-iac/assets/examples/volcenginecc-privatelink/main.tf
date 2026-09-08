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
  prefix  = "cc-iac-pl"
  zone_a  = "cn-beijing-a"
  zone_b  = "cn-beijing-b"
}

resource "volcenginecc_vpc_vpc" "service" {
  vpc_name     = "${local.prefix}-svc-vpc"
  description  = "volcenginecc PrivateLink service VPC"
  cidr_block   = "10.101.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
}

resource "volcenginecc_vpc_subnet" "service" {
  vpc_id      = volcenginecc_vpc_vpc.service.vpc_id
  zone_id     = local.zone_a
  subnet_name = "${local.prefix}-svc-subnet"
  description = "volcenginecc PrivateLink service subnet"
  cidr_block  = "10.101.1.0/24"
}

resource "volcenginecc_vpc_route_table" "service" {
  vpc_id           = volcenginecc_vpc_vpc.service.vpc_id
  route_table_name = "${local.prefix}-svc-rt"
  description      = "volcenginecc PrivateLink service route table"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids       = [volcenginecc_vpc_subnet.service.subnet_id]
}

resource "volcenginecc_clb_clb" "service" {
  load_balancer_name            = "${local.prefix}-clb"
  load_balancer_spec            = "small_1"
  address_ip_version            = "ipv4"
  bypass_security_group_enabled = "off"
  description                   = "volcenginecc PrivateLink service CLB"
  load_balancer_billing_type    = 2
  master_zone_id                = local.zone_a
  slave_zone_id                 = local.zone_b
  project_name                  = local.project
  subnet_id                     = volcenginecc_vpc_subnet.service.subnet_id
  type                          = "private"
  vpc_id                        = volcenginecc_vpc_vpc.service.vpc_id

  depends_on = [
    volcenginecc_vpc_route_table.service,
  ]
}

resource "volcenginecc_privatelink_endpoint_service" "main" {
  service_type          = "Interface"
  service_resource_type = "CLB"
  ip_address_versions   = ["ipv4"]
  auto_accept_enabled   = true
  private_dns_enabled   = false
  description           = "volcenginecc PrivateLink endpoint service"
  project_name          = local.project
  payer                 = "Endpoint"
  permit_account_ids    = ["*"]

  resources = [
    {
      resource_id = volcenginecc_clb_clb.service.load_balancer_id
      zone_ids    = [local.zone_a]
    }
  ]
}

resource "volcenginecc_vpc_vpc" "consumer" {
  vpc_name     = "${local.prefix}-ep-vpc"
  description  = "volcenginecc PrivateLink endpoint VPC"
  cidr_block   = "10.102.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
}

resource "volcenginecc_vpc_subnet" "consumer" {
  vpc_id      = volcenginecc_vpc_vpc.consumer.vpc_id
  zone_id     = local.zone_a
  subnet_name = "${local.prefix}-ep-subnet"
  description = "volcenginecc PrivateLink endpoint subnet"
  cidr_block  = "10.102.1.0/24"
}

resource "volcenginecc_vpc_route_table" "consumer" {
  vpc_id           = volcenginecc_vpc_vpc.consumer.vpc_id
  route_table_name = "${local.prefix}-ep-rt"
  description      = "volcenginecc PrivateLink endpoint route table"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids       = [volcenginecc_vpc_subnet.consumer.subnet_id]
}

resource "volcenginecc_vpc_security_group" "endpoint" {
  vpc_id              = volcenginecc_vpc_vpc.consumer.vpc_id
  security_group_name = "${local.prefix}-ep-sg"
  description         = "volcenginecc PrivateLink endpoint security group"
  project_name        = local.project
}

resource "volcenginecc_privatelink_vpc_endpoint" "main" {
  endpoint_name       = "${local.prefix}-endpoint"
  description         = "volcenginecc PrivateLink endpoint"
  private_dns_enabled = false
  project_name        = local.project
  security_group_ids  = [volcenginecc_vpc_security_group.endpoint.security_group_id]
  service_id          = volcenginecc_privatelink_endpoint_service.main.service_id
  service_name        = volcenginecc_privatelink_endpoint_service.main.service_name
  vpc_id              = volcenginecc_vpc_vpc.consumer.vpc_id

  zones = [
    {
      subnet_id = volcenginecc_vpc_subnet.consumer.subnet_id
      zone_id   = local.zone_a
    }
  ]

  depends_on = [
    volcenginecc_vpc_route_table.consumer,
  ]
}

output "service_id" {
  value = volcenginecc_privatelink_endpoint_service.main.service_id
}

output "service_name" {
  value = volcenginecc_privatelink_endpoint_service.main.service_name
}

output "clb_id" {
  value = volcenginecc_clb_clb.service.load_balancer_id
}

output "endpoint_id" {
  value = volcenginecc_privatelink_vpc_endpoint.main.endpoint_id
}
