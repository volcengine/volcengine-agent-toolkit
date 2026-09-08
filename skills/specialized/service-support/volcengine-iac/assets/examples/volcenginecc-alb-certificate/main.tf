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

variable "certificate_public_key" {
  description = "PEM encoded server certificate. Pass with TF_VAR_certificate_public_key; do not commit certificate material."
  type        = string
  sensitive   = true
}

variable "certificate_private_key" {
  description = "PEM encoded RSA private key. Pass with TF_VAR_certificate_private_key; this value is stored in Terraform state."
  type        = string
  sensitive   = true
}

locals {
  project = "default"
  prefix  = "cc-iac-alb-cert"
  tags = [
    {
      key   = "purpose"
      value = "terraform-volcenginecc-example"
    }
  ]
}

resource "volcenginecc_alb_certificate" "server" {
  certificate_name = "${local.prefix}-server"
  certificate_type = "Server"
  public_key       = var.certificate_public_key
  private_key      = var.certificate_private_key
  description      = "volcenginecc ALB server certificate example"
  project_name     = local.project
  tags             = local.tags
}

output "certificate_id" {
  value = volcenginecc_alb_certificate.server.certificate_id
}
