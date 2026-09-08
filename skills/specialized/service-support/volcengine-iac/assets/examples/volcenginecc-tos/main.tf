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
  project     = "default"
  bucket_name = "cc-iac-tos-example"
  tags = [
    {
      key   = "purpose"
      value = "terraform-volcenginecc-example"
    }
  ]
}

resource "volcenginecc_tos_bucket" "main" {
  name                  = local.bucket_name
  project_name          = local.project
  storage_class         = "STANDARD"
  bucket_type           = "fns"
  enable_version_status = "Enabled"
  tags                  = local.tags
}

resource "volcenginecc_tos_bucket_cors" "main" {
  bucket_name = volcenginecc_tos_bucket.main.name

  cors_rules = [
    {
      allowed_origins = ["https://example.com"]
      allowed_methods = ["GET", "PUT"]
      allowed_headers = ["Content-Type", "Authorization"]
      expose_headers  = ["x-tos-request-id"]
      max_age_seconds = 3600
      response_vary   = true
    }
  ]
}

resource "volcenginecc_tos_bucket_encryption" "main" {
  name          = volcenginecc_tos_bucket.main.name
  sse_algorithm = "AES256"
}

output "bucket_name" {
  value = volcenginecc_tos_bucket.main.name
}

output "intranet_endpoint" {
  value = volcenginecc_tos_bucket.main.intranet_endpoint
}

output "extranet_endpoint" {
  value = volcenginecc_tos_bucket.main.extranet_endpoint
}
