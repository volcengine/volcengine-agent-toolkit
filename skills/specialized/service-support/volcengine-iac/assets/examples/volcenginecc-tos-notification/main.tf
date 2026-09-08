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
  prefix      = "cc-iac-tos-noti"
  bucket_name = "cc-iac-tos-noti-example"

  # ZIP containing a root-level index.py with:
  # def handler(event, context):
  #     return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": "{\"ok\": true}"}
  function_zip_base64 = "UEsDBBQAAAAIAAQWvlwiFdCVfgAAAKYAAAAIABwAaW5kZXgucHlVVAkAA2jfGWpo3xlqdXgLAAEE9QEAAAQAAAAATYwxDsIwDEX3niLyBFIRFWPXXoGxS6iNWqjsKHEqqih3J4EB3mT//2yku5kt40r+QBuxtmYSVnrpsW9MwZNGzyZ9lgoEtRrDIEjQm0vXtb9qJovkQ8kTDPUN6+m6uyqCdW5dJquL8PkRhCH/Hd4E9yqlEeQ5lkl9pAxfIzdvUEsBAh4DFAAAAAgABBa+XCIV0JV+AAAApgAAAAgAGAAAAAAAAQAAAKSBAAAAAGluZGV4LnB5VVQFAANo3xlqdXgLAAEE9QEAAAQAAAAAUEsFBgAAAAABAAEATgAAAMAAAAAAAA=="

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

resource "volcenginecc_vefaas_function" "target" {
  name                      = "${local.prefix}-function"
  description               = "volcenginecc TOS notification target function"
  runtime                   = "python3.9/v1"
  source_type               = "zip"
  source                    = local.function_zip_base64
  memory_mb                 = 512
  request_timeout           = 30
  max_concurrency           = 10
  exclusive_mode            = false
  enable_apmplus            = false
  enable_dependency_install = false
  project_name              = local.project
  tags                      = local.tags

  lifecycle {
    ignore_changes = [
      source_type,
    ]
  }
}

resource "volcenginecc_vefaas_release" "target" {
  function_id           = volcenginecc_vefaas_function.target.function_id
  revision_number       = 0
  target_traffic_weight = 100
  rolling_step          = 100
  description           = "volcenginecc TOS notification function release"
  max_instance          = 1
}

resource "volcenginecc_tos_bucket_notification" "main" {
  bucket_name = volcenginecc_tos_bucket.main.name

  notification_rules = [
    {
      rule_id = "object-created-vefaas"
      events  = ["tos:ObjectCreated:Put"]
      destination = {
        ve_faa_s = [
          {
            function_id = volcenginecc_vefaas_function.target.function_id
          }
        ]
      }
      filter = {
        tos_key = {
          filter_rules = [
            {
              name  = "prefix"
              value = "events/"
            }
          ]
        }
      }
    }
  ]

  depends_on = [
    volcenginecc_vefaas_release.target,
  ]
}

output "bucket_name" {
  value = volcenginecc_tos_bucket.main.name
}

output "function_id" {
  value = volcenginecc_vefaas_function.target.function_id
}
