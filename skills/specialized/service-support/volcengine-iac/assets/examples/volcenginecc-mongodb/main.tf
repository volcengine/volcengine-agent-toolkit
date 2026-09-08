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

variable "mongodb_password" {
  type      = string
  sensitive = true
}

locals {
  project = "default"
  prefix  = "cc-iac-mongodb"
  zone_id = "cn-beijing-a"
}

resource "volcenginecc_vpc_vpc" "main" {
  vpc_name     = "${local.prefix}-vpc"
  description  = "volcenginecc MongoDB example VPC"
  cidr_block   = "10.95.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
}

resource "volcenginecc_vpc_subnet" "main" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = local.zone_id
  subnet_name = "${local.prefix}-subnet"
  description = "volcenginecc MongoDB example subnet"
  cidr_block  = "10.95.1.0/24"
}

resource "volcenginecc_vpc_route_table" "app" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${local.prefix}-rt"
  description      = "volcenginecc MongoDB example route table"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids       = [volcenginecc_vpc_subnet.main.subnet_id]
}

resource "volcenginecc_mongodb_allow_list" "app" {
  allow_list_name     = "${local.prefix}-allow"
  allow_list_type     = "IPv4"
  allow_list_category = "Ordinary"
  allow_list_desc     = "volcenginecc MongoDB allowlist example"
  project_name        = local.project
  allow_list          = ["10.0.0.0/8"]
}

resource "volcenginecc_mongodb_instance" "main" {
  zone_id                = local.zone_id
  vpc_id                 = volcenginecc_vpc_vpc.main.vpc_id
  subnet_id              = volcenginecc_vpc_subnet.main.subnet_id
  db_engine              = "MongoDB"
  db_engine_version      = "MongoDB_7_0"
  instance_type          = "ReplicaSet"
  node_spec              = "mongo.1c2g"
  node_number            = 3
  storage_space_gb       = 20
  super_account_name     = "root"
  super_account_password = var.mongodb_password
  instance_name          = "${local.prefix}-instance"
  instance_count         = 1
  charge_type            = "PostPaid"
  project_name           = local.project
  allow_list_ids         = [volcenginecc_mongodb_allow_list.app.allow_list_id]

  depends_on = [volcenginecc_vpc_route_table.app]
}

output "instance_id" {
  value = volcenginecc_mongodb_instance.main.id
}

output "allow_list_id" {
  value = volcenginecc_mongodb_allow_list.app.allow_list_id
}
