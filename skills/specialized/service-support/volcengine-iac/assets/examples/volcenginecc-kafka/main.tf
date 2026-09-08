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
  prefix  = "cc-iac-kafka"
  zone_id = "cn-beijing-a"
}

resource "volcenginecc_vpc_vpc" "main" {
  vpc_name     = "${local.prefix}-vpc"
  description  = "volcenginecc Kafka example VPC"
  cidr_block   = "10.97.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
}

resource "volcenginecc_vpc_subnet" "main" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = local.zone_id
  subnet_name = "${local.prefix}-subnet"
  description = "volcenginecc Kafka example subnet"
  cidr_block  = "10.97.1.0/24"
}

resource "volcenginecc_vpc_route_table" "app" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${local.prefix}-rt"
  description      = "volcenginecc Kafka example route table"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids       = [volcenginecc_vpc_subnet.main.subnet_id]
}

resource "volcenginecc_kafka_allow_list" "app" {
  allow_list_name = "${local.prefix}-allow"
  allow_list      = "10.97.0.0/16"
}

resource "volcenginecc_kafka_instance" "main" {
  compute_spec         = "kafka.20xrate.hw"
  instance_description = "volcenginecc Kafka example instance"
  instance_name        = "${local.prefix}-instance"
  subnet_id            = volcenginecc_vpc_subnet.main.subnet_id
  ip_white_list        = [volcenginecc_kafka_allow_list.app.allow_list_id]
  partition_number     = 350
  storage_space        = 300
  version              = "2.8.2"
  vpc_id               = volcenginecc_vpc_vpc.main.vpc_id
  zone_id              = local.zone_id
  project_name         = local.project

  charge_info = {
    charge_type = "PostPaid"
    auto_renew  = false
  }

  depends_on = [volcenginecc_vpc_route_table.app]
}

resource "volcenginecc_kafka_topic" "app" {
  instance_id      = volcenginecc_kafka_instance.main.instance_id
  topic_name       = "cc-iac-kafka-topic"
  partition_number = 3
  replica_number   = 3
}

output "instance_id" {
  value = volcenginecc_kafka_instance.main.instance_id
}

output "allow_list_id" {
  value = volcenginecc_kafka_allow_list.app.allow_list_id
}
