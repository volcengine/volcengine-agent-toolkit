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

variable "postgres_password" {
  type        = string
  sensitive   = true
  description = "Password for the PostgreSQL application account."
}

locals {
  project = "default"
  prefix  = "cc-iac-pg"
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
  description  = "volcenginecc RDS PostgreSQL example VPC"
  cidr_block   = "10.95.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
  tags         = local.tags
}

resource "volcenginecc_vpc_subnet" "main" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = local.zone
  subnet_name = "${local.prefix}-subnet"
  description = "volcenginecc RDS PostgreSQL example subnet"
  cidr_block  = "10.95.1.0/24"
  tags        = local.tags
}

resource "volcenginecc_vpc_route_table" "main" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${local.prefix}-rt"
  description      = "volcenginecc RDS PostgreSQL example route table"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids       = [volcenginecc_vpc_subnet.main.subnet_id]
  tags             = local.tags
}

resource "volcenginecc_rdspostgresql_allow_list" "app" {
  allow_list_name = "${local.prefix}-allow"
  allow_list_type = "IPv4"
  user_allow_list = "10.95.0.0/16"
}

resource "volcenginecc_rdspostgresql_instance" "main" {
  db_engine_version = "PostgreSQL_14"
  storage_type      = "LocalSSD"
  storage_space     = 100
  vpc_id            = volcenginecc_vpc_vpc.main.vpc_id
  subnet_id         = volcenginecc_vpc_subnet.main.subnet_id
  instance_name     = "${local.prefix}-instance"
  project_name      = local.project
  allow_list_ids    = [volcenginecc_rdspostgresql_allow_list.app.allow_list_id]
  tags              = local.tags

  charge_detail = {
    charge_type = "PostPaid"
  }

  node_info = [
    {
      zone_id   = local.zone
      node_spec = "rds.postgres.1c2g"
      node_type = "Primary"
    },
    {
      zone_id   = local.zone
      node_spec = "rds.postgres.1c2g"
      node_type = "Secondary"
    }
  ]

  depends_on = [
    volcenginecc_vpc_route_table.main,
  ]
}

resource "volcenginecc_rdspostgresql_db_account" "app" {
  instance_id        = volcenginecc_rdspostgresql_instance.main.instance_id
  account_name       = "appuser"
  account_password   = var.postgres_password
  account_type       = "Normal"
  account_privileges = "Inherit,Login"
}

resource "volcenginecc_rdspostgresql_database" "app" {
  instance_id        = volcenginecc_rdspostgresql_instance.main.instance_id
  db_name            = "appdb"
  character_set_name = "utf8"
  collate            = "C"
  c_type             = "C"
  owner              = volcenginecc_rdspostgresql_db_account.app.account_name
}

resource "volcenginecc_rdspostgresql_schema" "app" {
  instance_id = volcenginecc_rdspostgresql_instance.main.instance_id
  db_name     = volcenginecc_rdspostgresql_database.app.db_name
  schema_name = "appschema"
  owner       = volcenginecc_rdspostgresql_db_account.app.account_name
}

resource "volcenginecc_rdspostgresql_db_endpoint" "custom" {
  instance_id     = volcenginecc_rdspostgresql_instance.main.instance_id
  endpoint_name   = "${local.prefix}-custom"
  endpoint_type   = "Custom"
  nodes           = "Primary"
  read_write_mode = "ReadWrite"

  private_addresses = {
    domain_prefix  = "cciacpgextra"
    dns_visibility = false
    port           = "5432"
  }
}

resource "volcenginecc_rdspostgresql_backup" "manual" {
  instance_id        = volcenginecc_rdspostgresql_instance.main.instance_id
  backup_method      = "Logical"
  backup_scope       = "Database"
  backup_description = "volcenginecc PostgreSQL logical backup verification"

  backup_meta = [
    {
      db_name = volcenginecc_rdspostgresql_database.app.db_name
    }
  ]

  depends_on = [
    volcenginecc_rdspostgresql_database.app,
  ]
}

output "instance_id" {
  value = volcenginecc_rdspostgresql_instance.main.instance_id
}

output "custom_endpoint_id" {
  value = volcenginecc_rdspostgresql_db_endpoint.custom.endpoint_id
}

output "backup_id" {
  value = volcenginecc_rdspostgresql_backup.manual.backup_id
}

output "allow_list_id" {
  value = volcenginecc_rdspostgresql_allow_list.app.allow_list_id
}
