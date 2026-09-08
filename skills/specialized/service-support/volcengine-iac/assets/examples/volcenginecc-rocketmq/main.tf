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
  prefix  = "cc-iac-rocket"
  zone_id = "cn-beijing-a"
}

resource "volcenginecc_vpc_vpc" "main" {
  vpc_name     = "${local.prefix}-vpc"
  description  = "volcenginecc RocketMQ example VPC"
  cidr_block   = "10.99.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
}

resource "volcenginecc_vpc_subnet" "main" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = local.zone_id
  subnet_name = "${local.prefix}-subnet"
  description = "volcenginecc RocketMQ example subnet"
  cidr_block  = "10.99.1.0/24"
}

resource "volcenginecc_vpc_route_table" "app" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${local.prefix}-rt"
  description      = "volcenginecc RocketMQ example route table"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids       = [volcenginecc_vpc_subnet.main.subnet_id]
}

resource "volcenginecc_rocketmq_allow_list" "app" {
  allow_list_name = "${local.prefix}-allow"
  allow_list_type = "IPv4"
  allow_list      = "10.99.0.0/16"
}

resource "volcenginecc_rocketmq_instance" "main" {
  allow_list_ids       = [volcenginecc_rocketmq_allow_list.app.allow_list_id]
  ip_version_type      = "IPv4"
  enable_ssl           = false
  version              = "4.8"
  zone_id              = local.zone_id
  compute_spec         = "rocketmq.n1.x2.micro"
  storage_space        = 300
  vpc_id               = volcenginecc_vpc_vpc.main.vpc_id
  subnet_id            = volcenginecc_vpc_subnet.main.subnet_id
  file_reserved_time   = 24
  instance_name        = "${local.prefix}-instance"
  network_types        = "PrivateNetwork"
  project_name         = local.project
  instance_description = "volcenginecc RocketMQ example instance"

  charge_detail = {
    charge_type = "PostPaid"
  }

  depends_on = [volcenginecc_vpc_route_table.app]
}

resource "volcenginecc_rocketmq_topic" "app" {
  instance_id  = volcenginecc_rocketmq_instance.main.instance_id
  topic_name   = "cc-iac-rocket-topic"
  message_type = 0
  description  = "volcenginecc RocketMQ example topic"
  queue_number = 4
}

resource "volcenginecc_rocketmq_group" "app" {
  instance_id = volcenginecc_rocketmq_instance.main.instance_id
  group_id    = "GID_cc_iac_rocket"
  group_type  = "TCP"
  description = "volcenginecc RocketMQ example group"
}

output "instance_id" {
  value = volcenginecc_rocketmq_instance.main.instance_id
}

output "allow_list_id" {
  value = volcenginecc_rocketmq_allow_list.app.allow_list_id
}
