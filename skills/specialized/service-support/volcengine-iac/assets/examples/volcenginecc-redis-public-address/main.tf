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

variable "redis_password" {
  type      = string
  sensitive = true
}

locals {
  project = "default"
  prefix  = "cc-iac-redis-pub"
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
  description  = "volcenginecc Redis public endpoint example VPC"
  cidr_block   = "10.97.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
  tags         = local.tags
}

resource "volcenginecc_vpc_subnet" "primary" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = local.zone_id
  subnet_name = "${local.prefix}-subnet"
  description = "volcenginecc Redis public endpoint example subnet"
  cidr_block  = "10.97.1.0/24"
  tags        = local.tags
}

resource "volcenginecc_vpc_route_table" "app" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${local.prefix}-rt"
  description      = "volcenginecc Redis public endpoint example route table"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids       = [volcenginecc_vpc_subnet.primary.subnet_id]
  tags             = local.tags
}

resource "volcenginecc_vpc_eip" "redis" {
  name         = "${local.prefix}-eip"
  description  = "volcenginecc Redis public endpoint example EIP"
  isp          = "BGP"
  billing_type = 2
  bandwidth    = 1
  project_name = local.project
  tags         = local.tags
}

resource "volcenginecc_redis_allow_list" "app" {
  allow_list          = "127.0.0.1"
  allow_list_name     = "${local.prefix}-acl"
  allow_list_desc     = "volcenginecc Redis public endpoint example allow list"
  allow_list_category = "Ordinary"
  project_name        = local.project
}

resource "volcenginecc_redis_instance" "main" {
  instance_name       = "${local.prefix}-instance"
  project_name        = local.project
  vpc_id              = volcenginecc_vpc_vpc.main.vpc_id
  subnet_id           = volcenginecc_vpc_subnet.primary.subnet_id
  deletion_protection = "disabled"
  charge_type         = "PostPaid"
  engine_version      = "6.0"
  shard_capacity      = 512
  shard_number        = 1
  node_number         = 1
  sharded_cluster     = 0
  multi_az            = "disabled"
  port                = 6379
  no_auth_mode        = "close"
  password            = var.redis_password
  allow_list_ids      = [volcenginecc_redis_allow_list.app.allow_list_id]
  tags                = local.tags

  configure_nodes = [
    {
      az = local.zone_id
    }
  ]

  depends_on = [
    volcenginecc_vpc_route_table.app,
  ]
}

resource "volcenginecc_redis_endpoint_public_address" "main" {
  instance_id        = volcenginecc_redis_instance.main.instance_id
  eip_id             = volcenginecc_vpc_eip.redis.allocation_id
  port               = 6379
  new_address_prefix = "cciacredispub0530"
}

output "instance_id" {
  value = volcenginecc_redis_instance.main.instance_id
}

output "public_endpoint_address" {
  value = volcenginecc_redis_endpoint_public_address.main.address
}

output "eip_id" {
  value = volcenginecc_vpc_eip.redis.allocation_id
}
