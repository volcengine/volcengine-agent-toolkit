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
  prefix  = "cc-iac-vpn-ssl"
  tags = [
    {
      key   = "purpose"
      value = "terraform-volcenginecc-example"
    }
  ]
}

resource "volcenginecc_vpc_vpc" "main" {
  vpc_name     = "${local.prefix}-vpc"
  description  = "volcenginecc SSL VPN example VPC"
  cidr_block   = "172.30.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
  tags         = local.tags
}

resource "volcenginecc_vpc_subnet" "main" {
  subnet_name = "${local.prefix}-subnet-a"
  description = "volcenginecc SSL VPN example subnet"
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  cidr_block  = "172.30.10.0/24"
  zone_id     = "cn-beijing-a"
  tags        = local.tags
}

resource "volcenginecc_vpc_route_table" "main" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${local.prefix}-rt"
  description      = "volcenginecc SSL VPN example route table"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids       = [volcenginecc_vpc_subnet.main.subnet_id]
  tags             = local.tags
}

resource "volcenginecc_vpn_vpn_gateway" "main" {
  vpn_gateway_name    = "${local.prefix}-gateway"
  description         = "volcenginecc SSL VPN gateway example"
  project_name        = local.project
  vpc_id              = volcenginecc_vpc_vpc.main.vpc_id
  subnet_id           = volcenginecc_vpc_subnet.main.subnet_id
  bandwidth           = 5
  billing_type        = 2
  dual_tunnel_enabled = false
  ip_stack_type       = "ipv4_only"
  ip_version          = "ipv4"
  ipsec_enabled       = false
  ssl_enabled         = true
  ssl_max_connections = 5
  tags                = local.tags

  depends_on = [
    volcenginecc_vpc_route_table.main,
  ]
}

resource "volcenginecc_vpn_ssl_vpn_server" "main" {
  vpn_gateway_id             = volcenginecc_vpn_vpn_gateway.main.vpn_gateway_id
  ssl_vpn_server_name        = "${local.prefix}-server"
  description                = "volcenginecc SSL VPN server example"
  project_name               = local.project
  client_ip_pool             = "10.250.0.0/26"
  local_subnets              = ["172.30.0.0/16"]
  protocol                   = "TCP"
  port                       = 1194
  cipher                     = "AES-128-CBC"
  auth                       = "SHA1"
  compress                   = false
  client_cert_session_policy = "PreemptExisting"
  tags                       = local.tags
}

output "vpn_gateway_id" {
  value = volcenginecc_vpn_vpn_gateway.main.vpn_gateway_id
}

output "ssl_vpn_server_id" {
  value = volcenginecc_vpn_ssl_vpn_server.main.ssl_vpn_server_id
}
