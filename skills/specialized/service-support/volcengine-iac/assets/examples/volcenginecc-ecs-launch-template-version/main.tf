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
  prefix        = "cc-iac-ltv"
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
  description  = "volcenginecc launch template version example VPC"
  cidr_block   = "10.96.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
  tags         = local.tags
}

resource "volcenginecc_vpc_subnet" "primary" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = local.zone_id
  subnet_name = "${local.prefix}-subnet-a"
  description = "volcenginecc launch template version example subnet"
  cidr_block  = "10.96.1.0/24"
  tags        = local.tags
}

resource "volcenginecc_vpc_route_table" "app" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${local.prefix}-rt"
  description      = "volcenginecc launch template version example route table"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids       = [volcenginecc_vpc_subnet.primary.subnet_id]
  tags             = local.tags
}

resource "volcenginecc_vpc_security_group" "app" {
  vpc_id              = volcenginecc_vpc_vpc.main.vpc_id
  security_group_name = "${local.prefix}-sg"
  description         = "volcenginecc launch template version example security group"
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

resource "volcenginecc_ecs_launch_template" "main" {
  launch_template_name         = "${local.prefix}-lt"
  launch_template_project_name = local.project
  launch_template_tags         = local.tags
  launch_template_version = {
    description                   = "volcenginecc initial launch template version"
    image_id                      = local.image_id
    instance_charge_type          = "PostPaid"
    instance_name                 = "${local.prefix}-from-lt"
    instance_type_id              = local.instance_type
    project_name                  = local.project
    security_enhancement_strategy = "InActive"
    spot_strategy                 = "NoSpot"
    user_data                     = "ZWNobyBoZWxsby1mcm9tLWx0Cg=="
    version_description           = "initial verified version"
    vpc_id                        = volcenginecc_vpc_vpc.main.vpc_id
    zone_id                       = local.zone_id
    network_interfaces = [
      {
        security_group_ids = [volcenginecc_vpc_security_group.app.security_group_id]
        subnet_id          = volcenginecc_vpc_subnet.primary.subnet_id
      }
    ]
    tags = local.tags
  }
}

resource "volcenginecc_ecs_launch_template_version" "second" {
  launch_template_id            = volcenginecc_ecs_launch_template.main.launch_template_id
  description                   = "volcenginecc second launch template version"
  image_id                      = local.image_id
  instance_charge_type          = "PostPaid"
  instance_name                 = "${local.prefix}-second"
  instance_type_id              = local.instance_type
  project_name                  = local.project
  security_enhancement_strategy = "InActive"
  spot_strategy                 = "NoSpot"
  user_data                     = "ZWNobyBoZWxsby1mcm9tLWx0djIK"
  version_description           = "standalone verified version"
  vpc_id                        = volcenginecc_vpc_vpc.main.vpc_id
  zone_id                       = local.zone_id
  network_interfaces = [
    {
      security_group_ids = [volcenginecc_vpc_security_group.app.security_group_id]
      subnet_id          = volcenginecc_vpc_subnet.primary.subnet_id
    }
  ]
  tags = local.tags
}

output "launch_template_id" {
  value = volcenginecc_ecs_launch_template.main.launch_template_id
}

output "launch_template_version_number" {
  value = volcenginecc_ecs_launch_template_version.second.version_number
}
