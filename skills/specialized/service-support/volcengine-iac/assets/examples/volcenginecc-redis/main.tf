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
  prefix  = "cc-iac-redis"
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
  description  = "volcenginecc Redis example VPC"
  cidr_block   = "10.90.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
  tags         = local.tags
}

resource "volcenginecc_vpc_subnet" "primary" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = local.zone_id
  subnet_name = "${local.prefix}-subnet"
  description = "volcenginecc Redis example subnet"
  cidr_block  = "10.90.1.0/24"
  tags        = local.tags
}

resource "volcenginecc_vpc_route_table" "app" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${local.prefix}-rt"
  description      = "volcenginecc Redis example route table"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids       = [volcenginecc_vpc_subnet.primary.subnet_id]
  tags             = local.tags
}

resource "volcenginecc_redis_allow_list" "app" {
  allow_list          = "127.0.0.1"
  allow_list_name     = "${local.prefix}-acl"
  allow_list_desc     = "volcenginecc Redis example allow list"
  allow_list_category = "Ordinary"
  project_name        = local.project
}

resource "volcenginecc_redis_parameter_group" "app" {
  engine_version = "6.0"
  name           = "${local.prefix}-pg"
  description    = "volcenginecc Redis example parameter group"

  param_values = [
    {
      name  = "maxmemory-policy"
      value = "allkeys-lru"
    }
  ]
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
  parameter_group_id  = volcenginecc_redis_parameter_group.app.parameter_group_id
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

resource "volcenginecc_redis_account" "app" {
  instance_id  = volcenginecc_redis_instance.main.instance_id
  account_name = "appuser"
  description  = "volcenginecc Redis example account"
  password     = var.redis_password
  role_name    = "ReadWrite"
}

output "instance_id" {
  value = volcenginecc_redis_instance.main.instance_id
}

output "allow_list_id" {
  value = volcenginecc_redis_allow_list.app.allow_list_id
}

output "parameter_group_id" {
  value = volcenginecc_redis_parameter_group.app.parameter_group_id
}
