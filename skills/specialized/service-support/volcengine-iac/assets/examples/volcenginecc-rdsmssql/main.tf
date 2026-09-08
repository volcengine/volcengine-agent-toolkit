terraform {
  required_version = ">= 1.0.7"

  required_providers {
    volcenginecc = {
      source  = "volcengine/volcenginecc"
      version = "~> 0.0.46"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.12"
    }
  }
}

provider "volcenginecc" {}

variable "mssql_password" {
  type        = string
  sensitive   = true
  description = "Password for the SQL Server super account. This still lands in Terraform state."
}

locals {
  project = "default"
  prefix  = "cc-iac-mssql"
  zone    = "cn-beijing-a"
  tags = [
    {
      key   = "purpose"
      value = "terraform-volcenginecc-example"
    }
  ]
}

resource "volcenginecc_vpc_vpc" "main" {
  vpc_name     = "${local.prefix}-vpc"
  description  = "volcenginecc RDS SQL Server example VPC"
  cidr_block   = "10.98.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
  tags         = local.tags
}

resource "volcenginecc_vpc_subnet" "main" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = local.zone
  subnet_name = "${local.prefix}-subnet"
  description = "volcenginecc RDS SQL Server example subnet"
  cidr_block  = "10.98.1.0/24"
  tags        = local.tags
}

resource "volcenginecc_vpc_route_table" "main" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${local.prefix}-rt"
  description      = "volcenginecc RDS SQL Server example route table"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids       = [volcenginecc_vpc_subnet.main.subnet_id]
  tags             = local.tags
}

resource "time_sleep" "network_release_delay" {
  depends_on = [
    volcenginecc_rdsmssql_allow_list.app,
    volcenginecc_vpc_route_table.main,
  ]

  create_duration  = "60s"
  destroy_duration = "60s"
}

resource "volcenginecc_rdsmssql_allow_list" "app" {
  project_name        = local.project
  allow_list_name     = "${local.prefix}-allow"
  allow_list_desc     = "volcenginecc RDS SQL Server example allowlist"
  allow_list_type     = "IPv4"
  allow_list_category = "Ordinary"
  user_allow_list     = "10.98.0.0/16"
}

resource "volcenginecc_rdsmssql_instance" "main" {
  node_spec              = "rds.mssql.3il.x8.medium.s1"
  zone_id                = local.zone
  subnet_id              = volcenginecc_vpc_subnet.main.subnet_id
  db_engine_version      = "SQLServer_2019_Std"
  instance_type          = "Basic"
  storage_space          = 20
  vpc_id                 = volcenginecc_vpc_vpc.main.vpc_id
  instance_name          = "${local.prefix}-instance"
  super_account_password = var.mssql_password
  server_collation       = "Chinese_PRC_CI_AS"
  time_zone              = "China Standard Time"
  project_name           = local.project
  maintenance_time       = "18:00Z-21:59Z"
  allow_list_ids         = [volcenginecc_rdsmssql_allow_list.app.allow_list_id]

  charge_info = {
    charge_type = "PostPaid"
  }

  depends_on = [
    time_sleep.network_release_delay,
  ]
}

output "instance_id" {
  value = volcenginecc_rdsmssql_instance.main.instance_id
}

output "allow_list_id" {
  value = volcenginecc_rdsmssql_allow_list.app.allow_list_id
}
