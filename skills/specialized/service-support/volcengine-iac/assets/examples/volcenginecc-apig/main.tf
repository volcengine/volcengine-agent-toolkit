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
  prefix  = "cc-iac-apig"
  tags = [
    {
      key   = "purpose"
      value = "terraform-volcenginecc-example"
    }
  ]
}

resource "volcenginecc_vpc_vpc" "main" {
  vpc_name     = "${local.prefix}-vpc"
  description  = "volcenginecc APIG example VPC"
  cidr_block   = "172.30.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
  tags         = local.tags
}

resource "volcenginecc_vpc_subnet" "main" {
  subnet_name = "${local.prefix}-subnet-a"
  description = "volcenginecc APIG example subnet"
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  cidr_block  = "172.30.10.0/24"
  zone_id     = "cn-beijing-a"
  tags        = local.tags
}

resource "volcenginecc_apig_gateway" "main" {
  name         = "${local.prefix}-gateway"
  comments     = "volcenginecc APIG private gateway example"
  type         = "standard"
  project_name = local.project
  vpc_id       = volcenginecc_vpc_vpc.main.vpc_id
  subnet_ids   = [volcenginecc_vpc_subnet.main.subnet_id]

  resource_spec = {
    instance_spec_code       = "1c2g"
    replicas                 = 2
    public_network_bandwidth = 0
    network_type = {
      enable_public_network  = false
      enable_private_network = true
    }
  }
}

resource "volcenginecc_apig_gateway_service" "app" {
  service_name = "${local.prefix}-service"
  gateway_id   = volcenginecc_apig_gateway.main.gateway_id
  protocol     = ["HTTP"]
  comments     = "volcenginecc APIG private HTTP service example"

  auth_spec = {
    enable = false
  }

  service_network_spec = {
    enable_public_network  = false
    enable_private_network = true
  }
}

output "vpc_id" {
  value = volcenginecc_vpc_vpc.main.vpc_id
}

output "gateway_id" {
  value = volcenginecc_apig_gateway.main.gateway_id
}

output "service_id" {
  value = volcenginecc_apig_gateway_service.app.service_id
}

output "private_domains" {
  value = volcenginecc_apig_gateway_service.app.domains
}
