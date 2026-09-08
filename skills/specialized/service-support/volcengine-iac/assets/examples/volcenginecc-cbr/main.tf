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

resource "volcenginecc_cbr_vault" "app" {
  vault_name   = "cc-iac-cbr-vault"
  project_name = "default"
}

resource "volcenginecc_cbr_backup_policy" "app" {
  name              = "cc-iac-cbr-policy"
  backup_type       = "INCREMENTAL"
  crontab           = "0 2 * * 1"
  enable_policy     = false
  retention_day     = 7
  retention_num_max = -1
  retention_num_min = 2
}

output "vault_id" {
  value = volcenginecc_cbr_vault.app.id
}

output "backup_policy_id" {
  value = volcenginecc_cbr_backup_policy.app.id
}
