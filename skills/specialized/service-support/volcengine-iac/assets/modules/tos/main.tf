terraform {
  required_version = ">= 1.5"
  required_providers {
    volcengine = {
      source  = "volcengine/volcengine"
      version = "~> 0.0.196"
    }
  }
}

resource "volcengine_tos_bucket" "main" {
  bucket_name          = var.bucket_name
  public_acl           = var.public_acl
  storage_class        = var.storage_class
  enable_version       = var.versioning_enabled
  az_redundancy        = var.az_redundancy
  bucket_acl_delivered = false
  project_name         = var.project_name

  dynamic "tags" {
    for_each = var.tags
    content {
      key   = tags.key
      value = tags.value
    }
  }
}
