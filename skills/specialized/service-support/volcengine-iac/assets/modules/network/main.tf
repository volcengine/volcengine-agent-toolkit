terraform {
  required_version = ">= 1.5"
  required_providers {
    volcengine = {
      source  = "volcengine/volcengine"
      version = "~> 0.0.196"
    }
  }
}

resource "volcengine_vpc" "main" {
  vpc_name    = "${var.project}-vpc"
  cidr_block  = var.vpc_cidr
  description = "Managed by volcengine-iac for project ${var.project}"

  dynamic "tags" {
    for_each = var.tags
    content {
      key   = tags.key
      value = tags.value
    }
  }
}

resource "volcengine_subnet" "primary" {
  subnet_name = "${var.project}-subnet-primary"
  cidr_block  = var.subnet_cidr_primary
  zone_id     = var.az_primary
  vpc_id      = volcengine_vpc.main.id

  dynamic "tags" {
    for_each = var.tags
    content {
      key   = tags.key
      value = tags.value
    }
  }
}

resource "volcengine_subnet" "secondary" {
  subnet_name = "${var.project}-subnet-secondary"
  cidr_block  = var.subnet_cidr_secondary
  zone_id     = var.az_secondary
  vpc_id      = volcengine_vpc.main.id

  dynamic "tags" {
    for_each = var.tags
    content {
      key   = tags.key
      value = tags.value
    }
  }
}

resource "volcengine_security_group" "default" {
  vpc_id              = volcengine_vpc.main.id
  security_group_name = "${var.project}-default-sg"
  description         = "Default SG for ${var.project} (managed by volcengine-iac)"

  dynamic "tags" {
    for_each = var.tags
    content {
      key   = tags.key
      value = tags.value
    }
  }
}
