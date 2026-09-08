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
  prefix  = "cc-iac-cr"
  tags = [
    {
      key   = "purpose"
      value = "terraform-volcenginecc-example"
    }
  ]
}

resource "volcenginecc_cr_registry" "main" {
  project = local.project
  name    = local.prefix
  type    = "Enterprise"

  endpoint = {
    enabled = true
  }

  tags = local.tags
}

resource "volcenginecc_cr_name_space" "app" {
  registry = volcenginecc_cr_registry.main.name
  name     = "app"
  project  = local.project
}

resource "volcenginecc_cr_repository" "app" {
  registry     = volcenginecc_cr_registry.main.name
  namespace    = volcenginecc_cr_name_space.app.name
  name         = "demo"
  description  = "volcenginecc CR repository example"
  access_level = "Public"
}

resource "volcenginecc_cr_endpoint_acl_policy" "public" {
  registry    = volcenginecc_cr_registry.main.name
  type        = "Public"
  entry       = "0.0.0.0/0"
  description = "terraform volcenginecc CR endpoint ACL example"

  depends_on = [
    volcenginecc_cr_registry.main,
  ]
}

output "registry_name" {
  value = volcenginecc_cr_registry.main.name
}

output "namespace_name" {
  value = volcenginecc_cr_name_space.app.name
}

output "repository_name" {
  value = volcenginecc_cr_repository.app.name
}
