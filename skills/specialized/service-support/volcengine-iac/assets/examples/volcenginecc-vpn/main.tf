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

variable "vpn_psk" {
  description = "Pre-shared key for the example IPsec VPN connection."
  type        = string
  sensitive   = true
}

locals {
  project = "default"
  prefix  = "cc-iac-vpn"
  tags = [
    {
      key   = "purpose"
      value = "terraform-volcenginecc-example"
    }
  ]
}

resource "volcenginecc_vpc_vpc" "main" {
  vpc_name     = "${local.prefix}-vpc"
  description  = "volcenginecc VPN example VPC"
  cidr_block   = "172.31.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
  tags         = local.tags
}

resource "volcenginecc_vpc_subnet" "main" {
  subnet_name = "${local.prefix}-subnet-a"
  description = "volcenginecc VPN example subnet"
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  cidr_block  = "172.31.10.0/24"
  zone_id     = "cn-beijing-a"
  tags        = local.tags
}

resource "volcenginecc_vpc_route_table" "main" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${local.prefix}-rt"
  description      = "volcenginecc VPN example route table"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids       = [volcenginecc_vpc_subnet.main.subnet_id]
  tags             = local.tags
}

resource "volcenginecc_vpn_vpn_gateway" "main" {
  vpn_gateway_name    = "${local.prefix}-gateway"
  description         = "volcenginecc IPsec VPN gateway example"
  project_name        = local.project
  vpc_id              = volcenginecc_vpc_vpc.main.vpc_id
  subnet_id           = volcenginecc_vpc_subnet.main.subnet_id
  bandwidth           = 5
  billing_type        = 2
  dual_tunnel_enabled = false
  ip_stack_type       = "ipv4_only"
  ip_version          = "ipv4"
  ipsec_enabled       = true
  ssl_enabled         = false
  tags                = local.tags

  depends_on = [
    volcenginecc_vpc_route_table.main,
  ]
}

resource "volcenginecc_vpn_customer_gateway" "remote" {
  customer_gateway_name = "${local.prefix}-customer"
  description           = "volcenginecc customer gateway example"
  project_name          = local.project
  asn                   = 64513
  ip_address            = "0.0.0.0"
  ip_version            = "ipv4"
}

resource "volcenginecc_vpn_vpn_connection" "ipsec" {
  vpn_connection_name = "${local.prefix}-connection"
  description         = "volcenginecc IPsec VPN connection example"
  project_name        = local.project
  vpn_gateway_id      = volcenginecc_vpn_vpn_gateway.main.vpn_gateway_id
  customer_gateway_id = volcenginecc_vpn_customer_gateway.remote.customer_gateway_id
  attach_type         = "VpnGateway"
  local_subnet        = ["172.31.0.0/16"]
  remote_subnet       = ["192.168.200.0/24"]
  negotiate_instantly = false
  nat_traversal       = true
  dpd_action          = "restart"
  log_enabled         = false

  ike_config = {
    psk       = var.vpn_psk
    version   = "ikev1"
    mode      = "aggressive"
    auth_alg  = "sha1"
    enc_alg   = "aes"
    dh_group  = "group2"
    lifetime  = 86400
    local_id  = "0.0.0.0"
    remote_id = "0.0.0.0"
  }

  ipsec_config = {
    auth_alg = "sha1"
    enc_alg  = "aes"
    dh_group = "group2"
    lifetime = 86400
  }
}

resource "volcenginecc_vpn_vpn_gateway_route" "remote" {
  vpn_gateway_id         = volcenginecc_vpn_vpn_gateway.main.vpn_gateway_id
  next_hop_id            = volcenginecc_vpn_vpn_connection.ipsec.vpn_connection_id
  destination_cidr_block = "192.168.200.0/24"
}

output "vpc_id" {
  value = volcenginecc_vpc_vpc.main.vpc_id
}

output "vpn_gateway_id" {
  value = volcenginecc_vpn_vpn_gateway.main.vpn_gateway_id
}

output "customer_gateway_id" {
  value = volcenginecc_vpn_customer_gateway.remote.customer_gateway_id
}

output "vpn_connection_id" {
  value = volcenginecc_vpn_vpn_connection.ipsec.vpn_connection_id
}

output "vpn_gateway_route_id" {
  value = volcenginecc_vpn_vpn_gateway_route.remote.vpn_gateway_route_id
}
