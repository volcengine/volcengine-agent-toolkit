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
  region      = "cn-beijing"
  prefix      = "cc-iac-tls-import"
  bucket_name = "cc-iac-tls-import-example"
  tags = [
    {
      key   = "purpose"
      value = "terraform-volcenginecc-example"
    }
  ]
}

resource "volcenginecc_tls_project" "main" {
  project_name     = local.prefix
  description      = "volcenginecc TLS import task example project"
  iam_project_name = local.project
  tags             = local.tags
}

resource "volcenginecc_tls_topic" "target" {
  project_id    = volcenginecc_tls_project.main.project_id
  topic_name    = "${local.prefix}-target"
  description   = "volcenginecc TLS import task target topic"
  shard_count   = 1
  ttl           = 30
  auto_split    = false
  log_public_ip = false
  allow_consume = true
  tags          = local.tags
}

resource "volcenginecc_tls_index" "target" {
  topic_id          = volcenginecc_tls_topic.target.topic_id
  enable_auto_index = false
  max_text_len      = 2048

  full_text = {
    case_sensitive  = false
    delimiter       = " ,;:"
    include_chinese = true
  }
}

resource "volcenginecc_tos_bucket" "source" {
  name                  = local.bucket_name
  project_name          = local.project
  storage_class         = "STANDARD"
  bucket_type           = "fns"
  enable_version_status = "Enabled"
  tags                  = local.tags
}

resource "volcenginecc_tls_import_task" "tos" {
  task_name   = "${local.prefix}-tos"
  description = "volcenginecc TLS import task from TOS example"
  source_type = "tos"
  project_id  = volcenginecc_tls_project.main.project_id
  topic_id    = volcenginecc_tls_topic.target.topic_id

  import_source_info = {
    tos_source_info = {
      bucket        = volcenginecc_tos_bucket.source.name
      region        = local.region
      prefix        = "logs/"
      compress_type = "none"
    }
  }

  target_info = {
    region     = local.region
    log_type   = "json_log"
    log_sample = "{\"time\":\"2026-05-30 00:00:00\",\"level\":\"info\",\"message\":\"example\"}"
    extract_rule = {
      extract_rule = {
        time_key                = "time"
        time_format             = "%Y-%m-%d %H:%M:%S"
        time_sample             = "2026-05-30 00:00:00"
        un_match_log_key        = "LogParseFailed"
        un_match_up_load_switch = true
      }
      time_zone = "Asia/Shanghai"
    }
  }

  depends_on = [
    volcenginecc_tls_index.target,
  ]
}

output "task_id" {
  value = volcenginecc_tls_import_task.tos.task_id
}

output "bucket_name" {
  value = volcenginecc_tos_bucket.source.name
}
