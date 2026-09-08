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
  prefix  = "cc-iac-ebs-snap"
  tags = [
    {
      key   = "purpose"
      value = "terraform-volcenginecc-example"
    }
  ]
}

resource "volcenginecc_storageebs_volume" "data" {
  volume_name  = "${local.prefix}-vol"
  volume_type  = "ESSD_PL0"
  size         = 10
  zone_id      = "cn-beijing-a"
  pay_type     = "post"
  kind         = "data"
  project_name = local.project
  tags         = local.tags
}

resource "volcenginecc_storageebs_snapshot" "data" {
  volume_id     = volcenginecc_storageebs_volume.data.volume_id
  snapshot_name = "${local.prefix}-snapshot"
  project_name  = local.project
  tags          = local.tags
}

output "volume_id" {
  value = volcenginecc_storageebs_volume.data.volume_id
}

output "snapshot_id" {
  value = volcenginecc_storageebs_snapshot.data.snapshot_id
}
