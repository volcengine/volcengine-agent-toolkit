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
  prefix  = "cc-iac-tls"
  tags = [
    {
      key   = "purpose"
      value = "terraform-volcenginecc-example"
    }
  ]
}

resource "volcenginecc_tls_project" "main" {
  project_name     = local.prefix
  description      = "volcenginecc TLS example project"
  iam_project_name = local.project
  tags             = local.tags
}

resource "volcenginecc_tls_topic" "app" {
  project_id    = volcenginecc_tls_project.main.project_id
  topic_name    = "${local.prefix}-topic"
  description   = "volcenginecc TLS example topic"
  shard_count   = 1
  ttl           = 30
  auto_split    = false
  log_public_ip = false
  allow_consume = true
  tags          = local.tags
}

resource "volcenginecc_tls_index" "app" {
  topic_id          = volcenginecc_tls_topic.app.topic_id
  enable_auto_index = false
  max_text_len      = 2048

  full_text = {
    case_sensitive  = false
    delimiter       = " ,;:"
    include_chinese = true
  }

  key_value = [
    {
      key = "level"
      value = {
        auto_index_flag = false
        case_sensitive  = false
        delimiter       = " ,;:"
        include_chinese = false
        index_all       = false
        index_sql_all   = false
        sql_flag        = true
        value_type      = "text"
      }
    }
  ]
}

resource "volcenginecc_tls_rule" "host_file" {
  topic_id   = volcenginecc_tls_topic.app.topic_id
  rule_name  = "${local.prefix}-host-file"
  input_type = 0
  log_type   = "minimalist_log"
  paths      = ["/var/log/messages"]
}

resource "volcenginecc_tls_consumer_group" "app" {
  project_id          = volcenginecc_tls_project.main.project_id
  topic_id_list       = [volcenginecc_tls_topic.app.topic_id]
  consumer_group_name = "${local.prefix}-consumer-group"
  heartbeat_ttl       = 10
  ordered_consume     = false
}

output "project_id" {
  value = volcenginecc_tls_project.main.project_id
}

output "topic_id" {
  value = volcenginecc_tls_topic.app.topic_id
}

output "rule_id" {
  value = volcenginecc_tls_rule.host_file.rule_id
}

output "consumer_group_id" {
  value = volcenginecc_tls_consumer_group.app.id
}
