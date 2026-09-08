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
  prefix = "cc-iac-kafka-allow"
}

resource "volcenginecc_kafka_allow_list" "app" {
  allow_list_name = local.prefix
  allow_list      = "10.97.0.0/16"
}

output "allow_list_id" {
  value = volcenginecc_kafka_allow_list.app.allow_list_id
}
