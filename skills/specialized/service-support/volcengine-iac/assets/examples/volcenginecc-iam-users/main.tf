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
  prefix = "cc-iac-iam-users"
  tags = [
    {
      key   = "purpose"
      value = "terraform-volcenginecc-example"
    }
  ]
}

resource "volcenginecc_iam_group" "readers" {
  user_group_name = "${local.prefix}-group"
  display_name    = "cc iac iam users group"
  description     = "volcenginecc IAM group example"

  attached_policies = [
    {
      policy_name = "ReadOnlyAccess"
      policy_type = "System"
      policy_scope = [
        {
          policy_scope_type = "Global"
        }
      ]
    }
  ]
}

resource "volcenginecc_iam_user" "app" {
  user_name    = "${local.prefix}-user"
  display_name = "cc iac iam users app"
  description  = "volcenginecc IAM user example without login profile"
  groups       = [volcenginecc_iam_group.readers.user_group_name]

  policies = [
    {
      policy_name = "ReadOnlyAccess"
      policy_type = "System"
    }
  ]

  tags = local.tags
}

output "group_name" {
  value = volcenginecc_iam_group.readers.user_group_name
}

output "user_name" {
  value = volcenginecc_iam_user.app.user_name
}
