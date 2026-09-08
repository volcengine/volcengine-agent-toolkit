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
  prefix  = "cc-iac-ecs-extra"
  zone_id = "cn-beijing-a"
  tags = [
    {
      key   = "purpose"
      value = "terraform-volcenginecc-example"
    }
  ]
}

resource "volcenginecc_ecs_deployment_set" "availability" {
  deployment_set_name         = "${local.prefix}-dps"
  description                 = "volcenginecc ECS deployment set example"
  granularity                 = "host"
  strategy                    = "Availability"
  deployment_set_group_number = 1
}

resource "volcenginecc_ecs_hpc_cluster" "main" {
  name         = "${local.prefix}-hpc"
  zone_id      = local.zone_id
  description  = "volcenginecc ECS HPC cluster example"
  project_name = local.project
  tags         = local.tags
}

output "deployment_set_id" {
  value = volcenginecc_ecs_deployment_set.availability.deployment_set_id
}

output "hpc_cluster_id" {
  value = volcenginecc_ecs_hpc_cluster.main.hpc_cluster_id
}
