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
  prefix  = "cc-iac-pzone"
  tags = [
    {
      key   = "purpose"
      value = "terraform-volcenginecc-example"
    }
  ]
}

resource "volcenginecc_vpc_vpc" "main" {
  vpc_name     = "${local.prefix}-vpc"
  description  = "volcenginecc PrivateZone example VPC"
  cidr_block   = "10.97.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
  tags         = local.tags
}

resource "volcenginecc_vpc_subnet" "primary" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = "cn-beijing-a"
  subnet_name = "${local.prefix}-subnet-a"
  description = "volcenginecc PrivateZone example subnet a"
  cidr_block  = "10.97.1.0/24"
  tags        = local.tags
}

resource "volcenginecc_vpc_subnet" "secondary" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = "cn-beijing-b"
  subnet_name = "${local.prefix}-subnet-b"
  description = "volcenginecc PrivateZone example subnet b"
  cidr_block  = "10.97.2.0/24"
  tags        = local.tags
}

resource "volcenginecc_vpc_route_table" "app" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${local.prefix}-rt"
  description      = "volcenginecc PrivateZone example route table"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids = [
    volcenginecc_vpc_subnet.primary.subnet_id,
    volcenginecc_vpc_subnet.secondary.subnet_id,
  ]
  tags = local.tags
}

resource "volcenginecc_privatezone_private_zone" "main" {
  zone_name      = "svc.internal"
  project_name   = local.project
  line_mode      = 1
  recursion_mode = true
  remark         = "volcenginecc PrivateZone example"
  tags           = local.tags

  vpcs = [
    {
      vpc_id = volcenginecc_vpc_vpc.main.vpc_id
      region = "cn-beijing"
    }
  ]

  depends_on = [
    volcenginecc_vpc_route_table.app,
  ]
}

resource "volcenginecc_privatezone_record" "app" {
  zid    = tonumber(volcenginecc_privatezone_private_zone.main.zid)
  host   = "app"
  type   = "A"
  value  = "10.97.1.10"
  line   = "default"
  ttl    = 600
  enable = true
  remark = "app"
}

output "vpc_id" {
  value = volcenginecc_vpc_vpc.main.vpc_id
}

output "private_zone_id" {
  value = volcenginecc_privatezone_private_zone.main.zid
}

output "private_record_id" {
  value = volcenginecc_privatezone_record.app.record_id
}
