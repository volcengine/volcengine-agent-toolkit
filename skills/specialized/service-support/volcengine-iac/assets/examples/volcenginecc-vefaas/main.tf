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
  project = "default"
  prefix  = "cc-iac-vefaas"

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

resource "volcenginecc_vefaas_function" "main" {
  name                      = "${local.prefix}-function"
  description               = "volcenginecc veFaaS example function"
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

  envs = [
    {
      key   = "EXAMPLE_MODE"
      value = "terraform"
    }
  ]

  tags = local.tags

  lifecycle {
    ignore_changes = [
      source_type,
    ]
  }
}

resource "volcenginecc_vefaas_release" "main" {
  function_id           = volcenginecc_vefaas_function.main.function_id
  revision_number       = 0
  target_traffic_weight = 100
  rolling_step          = 100
  description           = "volcenginecc veFaaS example release"
  max_instance          = 1
}

resource "volcenginecc_vefaas_timer" "main" {
  function_id        = volcenginecc_vefaas_release.main.function_id
  name               = "${replace(local.prefix, "-", "_")}_timer"
  description        = "volcenginecc veFaaS example disabled timer"
  enabled            = false
  crontab            = "*/30 * * * *"
  payload            = jsonencode({ source = "terraform" })
  enable_concurrency = false
  retries            = 1
}

output "function_id" {
  value = volcenginecc_vefaas_function.main.function_id
}

output "release_record_id" {
  value = volcenginecc_vefaas_release.main.release_record_id
}

output "timer_id" {
  value = volcenginecc_vefaas_timer.main.timer_id
}
