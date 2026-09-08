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

variable "rabbitmq_password" {
  type      = string
  sensitive = true
}

locals {
  project = "default"
  prefix  = "cc-iac-rabbit"
  zone_id = "cn-beijing-a"
}

resource "volcenginecc_vpc_vpc" "main" {
  vpc_name     = "${local.prefix}-vpc"
  description  = "volcenginecc RabbitMQ example VPC"
  cidr_block   = "10.98.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
}

resource "volcenginecc_vpc_subnet" "main" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = local.zone_id
  subnet_name = "${local.prefix}-subnet"
  description = "volcenginecc RabbitMQ example subnet"
  cidr_block  = "10.98.1.0/24"
}

resource "volcenginecc_vpc_route_table" "app" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${local.prefix}-rt"
  description      = "volcenginecc RabbitMQ example route table"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids       = [volcenginecc_vpc_subnet.main.subnet_id]
}

resource "volcenginecc_rabbitmq_allow_list" "app" {
  allow_list_type = "IPv4"
  allow_list      = "10.98.0.0/16"
  allow_list_name = "${local.prefix}-allow"
}

resource "volcenginecc_rabbitmq_instance" "main" {
  zone_id              = local.zone_id
  user_name            = "ccrabbituser"
  user_password        = var.rabbitmq_password
  compute_spec         = "rabbitmq.n1.x4.small"
  version              = "3.12"
  storage_space        = 100
  instance_description = "volcenginecc RabbitMQ example instance"
  instance_name        = "${local.prefix}-instance"
  vpc_id               = volcenginecc_vpc_vpc.main.vpc_id
  subnet_id            = volcenginecc_vpc_subnet.main.subnet_id
  project_name         = local.project

  charge_detail = {
    charge_type = "PostPaid"
  }

  depends_on = [volcenginecc_vpc_route_table.app]
}

output "instance_id" {
  value = volcenginecc_rabbitmq_instance.main.instance_id
}

output "allow_list_id" {
  value = volcenginecc_rabbitmq_allow_list.app.allow_list_id
}
