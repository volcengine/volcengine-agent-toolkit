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
  prefix        = "cc-iac-ecs"
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
  description  = "volcenginecc ECS example VPC"
  cidr_block   = "10.89.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
  tags         = local.tags
}

resource "volcenginecc_vpc_subnet" "primary" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = local.zone_id
  subnet_name = "${local.prefix}-subnet-a"
  description = "volcenginecc ECS example subnet"
  cidr_block  = "10.89.1.0/24"
  tags        = local.tags
}

resource "volcenginecc_vpc_route_table" "app" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${local.prefix}-rt"
  description      = "volcenginecc ECS example route table"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids       = [volcenginecc_vpc_subnet.primary.subnet_id]
  tags             = local.tags
}

resource "volcenginecc_vpc_security_group" "app" {
  vpc_id              = volcenginecc_vpc_vpc.main.vpc_id
  security_group_name = "${local.prefix}-sg"
  description         = "volcenginecc ECS example security group"
  project_name        = local.project

  ingress_permissions = [
    {
      description     = "allow-http"
      direction       = "ingress"
      policy          = "accept"
      priority        = 1
      protocol        = "tcp"
      port_start      = 80
      port_end        = 80
      cidr_ip         = "0.0.0.0/0"
      prefix_list_id  = ""
      source_group_id = ""
    }
  ]

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
  description   = "volcenginecc ECS example keypair"
  tags          = local.tags
}

resource "volcenginecc_storageebs_volume" "data" {
  volume_name  = "${local.prefix}-data"
  volume_type  = "ESSD_PL0"
  size         = 10
  zone_id      = local.zone_id
  pay_type     = "post"
  project_name = local.project
  tags         = local.tags
}

resource "volcenginecc_ecs_command" "hello" {
  name            = "${local.prefix}-hello"
  type            = "Shell"
  command_content = "ZWNobyB2b2xjZW5naW5lY2MtZWNzLW9r"
  description     = "volcenginecc ECS example command"
  project_name    = local.project
  timeout         = 60
  username        = "root"
  working_dir     = "/tmp"
  tags            = local.tags
}

resource "volcenginecc_ecs_launch_template" "main" {
  launch_template_name         = "${local.prefix}-lt"
  launch_template_project_name = local.project
  launch_template_tags         = local.tags
  launch_template_version = {
    description                   = "volcenginecc ECS example launch template"
    image_id                      = local.image_id
    instance_charge_type          = "PostPaid"
    instance_name                 = "${local.prefix}-from-lt"
    instance_type_id              = local.instance_type
    key_pair_name                 = volcenginecc_ecs_keypair.main.key_pair_name
    project_name                  = local.project
    security_enhancement_strategy = "InActive"
    spot_strategy                 = "NoSpot"
    user_data                     = "ZWNobyBoZWxsby1mcm9tLWxhdW5jaC10ZW1wbGF0ZQo="
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

resource "volcenginecc_ecs_instance" "main" {
  instance_name             = "${local.prefix}-instance"
  hostname                  = "cc-iac-ecs"
  description               = "volcenginecc ECS example instance"
  instance_charge_type      = "PostPaid"
  instance_type             = local.instance_type
  zone_id                   = local.zone_id
  project_name              = local.project
  spot_strategy             = "NoSpot"
  deletion_protection       = false
  install_run_command_agent = true

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

output "key_pair_name" {
  value = volcenginecc_ecs_keypair.main.key_pair_name
}

output "volume_id" {
  value = volcenginecc_storageebs_volume.data.volume_id
}

output "command_id" {
  value = volcenginecc_ecs_command.hello.command_id
}

output "launch_template_id" {
  value = volcenginecc_ecs_launch_template.main.launch_template_id
}

output "instance_id" {
  value = volcenginecc_ecs_instance.main.instance_id
}
