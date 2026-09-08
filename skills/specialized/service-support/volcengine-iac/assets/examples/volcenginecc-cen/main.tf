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
  description = "Volcengine account ID that owns the VPC attached to CEN."
}

locals {
  project = "default"
  prefix  = "cc-iac-cen"
  region  = "cn-beijing"
}

resource "volcenginecc_vpc_vpc" "main" {
  vpc_name     = "${local.prefix}-vpc"
  description  = "volcenginecc CEN example VPC"
  cidr_block   = "10.98.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
}

resource "volcenginecc_cen_cen" "main" {
  cen_name     = "${local.prefix}-cen"
  description  = "volcenginecc CEN example"
  project_name = local.project

  instances = [
    {
      instance_id        = volcenginecc_vpc_vpc.main.vpc_id
      instance_owner_id  = var.account_id
      instance_region_id = local.region
      instance_type      = "VPC"
    }
  ]
}

output "vpc_id" {
  value = volcenginecc_vpc_vpc.main.vpc_id
}

output "cen_id" {
  value = volcenginecc_cen_cen.main.cen_id
}
