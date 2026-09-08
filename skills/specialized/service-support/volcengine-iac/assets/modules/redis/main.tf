terraform {
  required_version = ">= 1.5"
  required_providers {
    volcengine = {
      source  = "volcengine/volcengine"
      version = "~> 0.0.196"
    }
  }
}

resource "volcengine_redis_instance" "main" {
  instance_name   = "${var.project}-redis"
  engine_version  = var.engine_version
  subnet_id       = var.subnet_id
  charge_type     = var.charge_type
  multi_az        = var.multi_az
  sharded_cluster = var.sharded_cluster
  node_number     = var.node_number
  shard_capacity  = var.shard_capacity
  port            = var.port

  configure_nodes {
    az = var.primary_az
  }

  dynamic "configure_nodes" {
    for_each = var.multi_az == "enabled" ? [1] : []
    content {
      az = var.secondary_az
    }
  }

  dynamic "tags" {
    for_each = var.tags
    content {
      key   = tags.key
      value = tags.value
    }
  }
}
