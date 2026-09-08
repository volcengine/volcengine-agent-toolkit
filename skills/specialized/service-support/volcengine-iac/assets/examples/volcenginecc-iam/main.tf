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

variable "account_id" {
  type        = string
  description = "Volcengine account ID used in the role trust policy root principal."
}

locals {
  project = "default"
  prefix  = "cc-iac-iam"
  tags = [
    {
      key   = "purpose"
      value = "terraform-volcenginecc-example"
    }
  ]
}

resource "volcenginecc_iam_project" "main" {
  project_name        = local.prefix
  display_name        = "cc iac iam example"
  description         = "volcenginecc IAM example project"
  parent_project_name = local.project
}

resource "volcenginecc_iam_role" "main" {
  role_name            = "${local.prefix}-role"
  display_name         = "cc iac iam example role"
  description          = "volcenginecc IAM example role"
  max_session_duration = 3600
  trust_policy_document = jsonencode({
    Statement = [
      {
        Effect = "Allow"
        Action = ["sts:AssumeRole"]
        Principal = {
          IAM = ["trn:iam::${var.account_id}:root"]
        }
      }
    ]
  })
  tags = local.tags
}

resource "volcenginecc_iam_policy" "main" {
  policy_name = "${local.prefix}-policy"
  policy_type = "Custom"
  description = "volcenginecc IAM example policy"
  policy_document = jsonencode({
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["vpc:DescribeVpcs"]
        Resource = ["*"]
      }
    ]
  })
}

output "project_name" {
  value = volcenginecc_iam_project.main.project_name
}

output "role_name" {
  value = volcenginecc_iam_role.main.role_name
}

output "policy_name" {
  value = volcenginecc_iam_policy.main.policy_name
}
