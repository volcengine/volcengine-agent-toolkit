terraform {
  required_version = ">= 1.5"
  required_providers {
    volcengine = {
      source  = "volcengine/volcengine"
      version = "~> 0.0.196"
    }
  }
}

resource "volcengine_cr_registry" "main" {
  name = var.registry_name
  type = var.registry_type
}

resource "volcengine_cr_namespace" "main" {
  registry = volcengine_cr_registry.main.name
  name     = var.namespace
  project  = var.project
}

resource "volcengine_cr_repository" "main" {
  registry     = volcengine_cr_registry.main.name
  namespace    = volcengine_cr_namespace.main.name
  name         = var.repository_name
  access_level = var.access_level
  description  = "Managed by volcengine-iac for project ${var.project}"
}
