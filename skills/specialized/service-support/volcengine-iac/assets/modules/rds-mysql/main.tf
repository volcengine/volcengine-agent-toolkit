terraform {
  required_version = ">= 1.5"
  required_providers {
    volcengine = {
      source  = "volcengine/volcengine"
      version = "~> 0.0.196"
    }
  }
}

resource "volcengine_rds_mysql_instance" "main" {
  instance_name     = "${var.project}-mysql"
  db_engine_version = var.db_engine_version
  primary_zone_id   = var.primary_zone_id
  secondary_zone_id = var.secondary_zone_id
  subnet_id         = var.subnet_id
  storage_space     = var.storage_space

  charge_info {
    charge_type = var.charge_type
  }

  node_spec {
    spec_name = var.instance_type
  }

  dynamic "tags" {
    for_each = var.tags
    content {
      key   = tags.key
      value = tags.value
    }
  }
}
