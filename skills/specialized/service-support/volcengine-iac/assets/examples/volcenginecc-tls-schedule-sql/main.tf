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
  prefix  = "cc-iac-tls-sql"
}

resource "volcenginecc_tls_project" "main" {
  project_name     = local.prefix
  description      = "volcenginecc TLS schedule SQL example project"
  iam_project_name = local.project
}

resource "volcenginecc_tls_topic" "source" {
  project_id    = volcenginecc_tls_project.main.project_id
  topic_name    = "${local.prefix}-source"
  description   = "volcenginecc TLS schedule SQL source topic"
  shard_count   = 1
  ttl           = 30
  auto_split    = false
  log_public_ip = false
  allow_consume = false
}

resource "volcenginecc_tls_topic" "dest" {
  project_id    = volcenginecc_tls_project.main.project_id
  topic_name    = "${local.prefix}-dest"
  description   = "volcenginecc TLS schedule SQL destination topic"
  shard_count   = 1
  ttl           = 30
  auto_split    = false
  log_public_ip = false
  allow_consume = false
}

resource "volcenginecc_tls_index" "source" {
  topic_id          = volcenginecc_tls_topic.source.topic_id
  enable_auto_index = false
  max_text_len      = 2048

  full_text = {
    case_sensitive  = false
    delimiter       = " ,;:"
    include_chinese = true
  }
}

resource "volcenginecc_tls_index" "dest" {
  topic_id          = volcenginecc_tls_topic.dest.topic_id
  enable_auto_index = false
  max_text_len      = 2048

  full_text = {
    case_sensitive  = false
    delimiter       = " ,;:"
    include_chinese = true
  }
}

resource "volcenginecc_tls_schedule_sql_task" "main" {
  task_name           = "${local.prefix}-task"
  description         = "volcenginecc TLS schedule SQL example"
  task_type           = 0
  source_topic_id     = volcenginecc_tls_topic.source.topic_id
  dest_topic_id       = volcenginecc_tls_topic.dest.topic_id
  dest_region         = "cn-beijing"
  query               = "* | SELECT count(*) AS count"
  status              = 0
  process_start_time  = 1780096500
  process_end_time    = 1780097100
  process_sql_delay   = 60
  process_time_window = "@m-15m,@m"

  depends_on = [
    volcenginecc_tls_index.source,
    volcenginecc_tls_index.dest,
  ]

  request_cycle = {
    type = "Period"
    time = 15
  }
}

output "task_id" {
  value = volcenginecc_tls_schedule_sql_task.main.task_id
}
