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

variable "mysql_password" {
  type        = string
  sensitive   = true
  description = "Password for the MySQL super account and example app account."
}

locals {
  project = "default"
  prefix  = "cc-iac-mysql"
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
  description  = "volcenginecc RDS MySQL example VPC"
  cidr_block   = "10.94.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
  tags         = local.tags
}

resource "volcenginecc_vpc_subnet" "main" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = local.zone
  subnet_name = "${local.prefix}-subnet"
  description = "volcenginecc RDS MySQL example subnet"
  cidr_block  = "10.94.1.0/24"
  tags        = local.tags
}

resource "volcenginecc_vpc_route_table" "main" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${local.prefix}-rt"
  description      = "volcenginecc RDS MySQL example route table"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids       = [volcenginecc_vpc_subnet.main.subnet_id]
  tags             = local.tags
}

resource "volcenginecc_rdsmysql_allow_list" "app" {
  allow_list_name = "${local.prefix}-allow"
  allow_list_type = "IPv4"
  user_allow_list = ["10.94.0.0/16"]
  project_name    = local.project
}

resource "volcenginecc_rdsmysql_parameter_template" "app" {
  template_name         = "${local.prefix}-params"
  template_type         = "Mysql"
  template_type_version = "MySQL_5_7"
  engine_type           = "InnoDB"
  template_desc         = "volcenginecc RDS MySQL example parameter template"
  project_name          = local.project

  template_params = [
    {
      name          = "auto_increment_increment"
      running_value = "1"
    }
  ]
}

resource "volcenginecc_rdsmysql_instance" "main" {
  deletion_protection    = "Disabled"
  db_engine_version      = "MySQL_5_7"
  storage_type           = "CloudESSD_PL0"
  storage_space          = 100
  instance_type          = "DoubleNode"
  vpc_id                 = volcenginecc_vpc_vpc.main.vpc_id
  subnet_id              = volcenginecc_vpc_subnet.main.subnet_id
  instance_name          = "${local.prefix}-instance"
  super_account_name     = "adminuser"
  super_account_password = var.mysql_password
  lower_case_table_names = "1"
  db_time_zone           = "UTC +08:00"
  allow_list_ids         = [volcenginecc_rdsmysql_allow_list.app.allow_list_id]
  port                   = 3306
  project_name           = local.project
  tags                   = local.tags

  charge_detail = {
    charge_type = "PostPaid"
    auto_renew  = false
    number      = 1
  }

  nodes = [
    {
      zone_id   = local.zone
      node_spec = "rds.mysql.c.s.1c2g"
      node_type = "Primary"
    },
    {
      zone_id   = local.zone
      node_spec = "rds.mysql.c.s.1c2g"
      node_type = "Secondary"
    }
  ]

  depends_on = [
    volcenginecc_vpc_route_table.main,
  ]
}

resource "volcenginecc_rdsmysql_database" "app" {
  instance_id        = volcenginecc_rdsmysql_instance.main.instance_id
  name               = "appdb"
  character_set_name = "utf8mb4"
  description        = "volcenginecc RDS MySQL example database"
}

resource "volcenginecc_rdsmysql_db_account" "app" {
  instance_id      = volcenginecc_rdsmysql_instance.main.instance_id
  account_name     = "appuser"
  account_password = var.mysql_password
  account_type     = "Normal"
  account_desc     = "volcenginecc RDS MySQL example app account"
  host             = "%"

  account_privileges = [
    {
      account_privilege        = "Custom"
      account_privilege_detail = ["SELECT", "INSERT", "UPDATE", "DELETE"]
      db_name                  = volcenginecc_rdsmysql_database.app.name
    },
    {
      account_privilege        = "Global"
      account_privilege_detail = ["PROCESS", "REPLICATION CLIENT", "REPLICATION SLAVE"]
      db_name                  = ""
    }
  ]
}

output "instance_id" {
  value = volcenginecc_rdsmysql_instance.main.instance_id
}

output "allow_list_id" {
  value = volcenginecc_rdsmysql_allow_list.app.allow_list_id
}

output "parameter_template_id" {
  value = volcenginecc_rdsmysql_parameter_template.app.template_id
}
