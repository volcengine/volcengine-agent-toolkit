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
  project       = "default"
  prefix        = "cc-iac-ebs-sg"
  zone_id       = "cn-beijing-a"
  image_id      = "image-z0dpqndnmy8rpzcad9rz"
  instance_type = "ecs.g4i.large"
  tags = [
    {
      key   = "purpose"
      value = "terraform-volcenginecc-example"
    }
  ]
}

resource "volcenginecc_vpc_vpc" "main" {
  vpc_name     = "${local.prefix}-vpc"
  description  = "volcenginecc EBS snapshot group example VPC"
  cidr_block   = "10.106.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
  tags         = local.tags
}

resource "volcenginecc_vpc_subnet" "primary" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = local.zone_id
  subnet_name = "${local.prefix}-subnet-a"
  description = "volcenginecc EBS snapshot group example subnet"
  cidr_block  = "10.106.1.0/24"
  tags        = local.tags
}

resource "volcenginecc_vpc_route_table" "app" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${local.prefix}-rt"
  description      = "volcenginecc EBS snapshot group example route table"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids       = [volcenginecc_vpc_subnet.primary.subnet_id]
  tags             = local.tags
}

resource "volcenginecc_vpc_security_group" "app" {
  vpc_id              = volcenginecc_vpc_vpc.main.vpc_id
  security_group_name = "${local.prefix}-sg"
  description         = "volcenginecc EBS snapshot group example security group"
  project_name        = local.project

  egress_permissions = [
    {
      description     = "allow-all-egress"
      direction       = "egress"
      policy          = "accept"
      priority        = 1
      protocol        = "all"
      port_start      = -1
      port_end        = -1
      cidr_ip         = "0.0.0.0/0"
      prefix_list_id  = ""
      source_group_id = ""
    }
  ]

  tags = local.tags

  depends_on = [
    volcenginecc_vpc_route_table.app,
  ]
}

resource "volcenginecc_ecs_keypair" "main" {
  key_pair_name = "${local.prefix}-key"
  project_name  = local.project
  description   = "volcenginecc EBS snapshot group example keypair"
  tags          = local.tags
}

resource "volcenginecc_ecs_instance" "main" {
  instance_name        = "${local.prefix}-instance"
  hostname             = "cc-iac-ebs-sg"
  description          = "volcenginecc EBS snapshot group example instance"
  instance_charge_type = "PostPaid"
  instance_type        = local.instance_type
  zone_id              = local.zone_id
  project_name         = local.project
  spot_strategy        = "NoSpot"
  deletion_protection  = false

  image = {
    image_id                      = local.image_id
    security_enhancement_strategy = "InActive"
  }

  key_pair = {
    key_pair_name = volcenginecc_ecs_keypair.main.key_pair_name
  }

  primary_network_interface = {
    security_group_ids = [volcenginecc_vpc_security_group.app.security_group_id]
    subnet_id          = volcenginecc_vpc_subnet.primary.subnet_id
  }

  system_volume = {
    delete_with_instance = true
    size                 = 20
    volume_type          = "ESSD_PL0"
  }

  tags = local.tags

  lifecycle {
    ignore_changes = all
  }
}

resource "volcenginecc_storageebs_snapshot_group" "system" {
  name         = "${local.prefix}-snap-group"
  project_name = local.project
  instance_id  = volcenginecc_ecs_instance.main.instance_id
  volume_ids   = [volcenginecc_ecs_instance.main.system_volume.volume_id]
  tags         = local.tags
}

output "instance_id" {
  value = volcenginecc_ecs_instance.main.instance_id
}

output "system_volume_id" {
  value = volcenginecc_ecs_instance.main.system_volume.volume_id
}

output "snapshot_group_id" {
  value = volcenginecc_storageebs_snapshot_group.system.snapshot_group_id
}
