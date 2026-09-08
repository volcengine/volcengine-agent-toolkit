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

variable "scheduled_launch_time" {
  type        = string
  description = "One-off launch time for the scheduled scaling policy. Must be a near-future UTC timestamp in YYYY-MM-DDTHH:MMZ form, within the Auto Scaling scheduling window (a few days out, not years). Times far in the future fail with InvalidScheduledPolicyLaunchTime.Malformed."
}

locals {
  project       = "default"
  prefix        = "cc-iac-as"
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
  description  = "volcenginecc Auto Scaling example VPC"
  cidr_block   = "10.107.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
  tags         = local.tags
}

resource "volcenginecc_vpc_subnet" "primary" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = local.zone_id
  subnet_name = "${local.prefix}-subnet-a"
  description = "volcenginecc Auto Scaling example subnet"
  cidr_block  = "10.107.1.0/24"
  tags        = local.tags
}

resource "volcenginecc_vpc_route_table" "app" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${local.prefix}-rt"
  description      = "volcenginecc Auto Scaling example route table"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids       = [volcenginecc_vpc_subnet.primary.subnet_id]
  tags             = local.tags
}

resource "volcenginecc_vpc_security_group" "app" {
  vpc_id              = volcenginecc_vpc_vpc.main.vpc_id
  security_group_name = "${local.prefix}-sg"
  description         = "volcenginecc Auto Scaling example security group"
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
  description   = "volcenginecc Auto Scaling example keypair"
  tags          = local.tags
}

resource "volcenginecc_ecs_launch_template" "main" {
  launch_template_name         = "${local.prefix}-lt"
  launch_template_project_name = local.project
  launch_template_tags         = local.tags
  launch_template_version = {
    description                   = "volcenginecc Auto Scaling example launch template"
    image_id                      = local.image_id
    instance_charge_type          = "PostPaid"
    instance_name                 = "${local.prefix}-from-lt"
    instance_type_id              = local.instance_type
    key_pair_name                 = volcenginecc_ecs_keypair.main.key_pair_name
    project_name                  = local.project
    security_enhancement_strategy = "InActive"
    spot_strategy                 = "NoSpot"
    user_data                     = "ZWNobyBoZWxsby1mcm9tLWF1dG9zY2FsaW5nLWxhdW5jaC10ZW1wbGF0ZQo="
    version_description           = "initial verified version"
    vpc_id                        = volcenginecc_vpc_vpc.main.vpc_id
    zone_id                       = local.zone_id
    network_interfaces = [
      {
        security_group_ids = [volcenginecc_vpc_security_group.app.security_group_id]
        subnet_id          = volcenginecc_vpc_subnet.primary.subnet_id
      }
    ]
    volumes = [
      {
        delete_with_instance            = true
        extra_performance_iops          = 0
        extra_performance_throughput_mb = 0
        extra_performance_type_id       = ""
        size                            = 20
        snapshot_id                     = ""
        volume_type                     = "ESSD_PL0"
      }
    ]
    tags = local.tags
  }
}

resource "volcenginecc_autoscaling_scaling_group" "app" {
  scaling_group_name      = "${local.prefix}-group"
  subnet_ids              = [volcenginecc_vpc_subnet.primary.subnet_id]
  min_instance_number     = 0
  max_instance_number     = 0
  desire_instance_number  = 0
  default_cooldown        = 300
  health_check_type       = "ECS"
  scaling_mode            = "release"
  multi_az_policy         = "PRIORITY"
  is_enable_scaling_group = false
  launch_template_id      = volcenginecc_ecs_launch_template.main.launch_template_id
  launch_template_version = "Default"
  project_name            = local.project
  tags                    = local.tags

  depends_on = [
    volcenginecc_ecs_launch_template.main,
    volcenginecc_vpc_route_table.app,
  ]
}

resource "volcenginecc_autoscaling_scaling_configuration" "app" {
  scaling_group_id           = volcenginecc_autoscaling_scaling_group.app.scaling_group_id
  scaling_configuration_name = "${local.prefix}-config"
  instance_name              = "${local.prefix}-instance"
  host_name                  = "cc-iac-as"
  image_id                   = local.image_id
  security_group_ids         = [volcenginecc_vpc_security_group.app.security_group_id]
  key_pair_name              = volcenginecc_ecs_keypair.main.key_pair_name
  instance_type_overrides = [
    {
      instance_type = local.instance_type
      price_limit   = 0
    }
  ]
  security_enhancement_strategy = "InActive"
  spot_strategy                 = "NoSpot"
  zone_id                       = local.zone_id
  project_name                  = local.project
  user_data                     = "ZWNobyB2b2xjZW5naW5lY2MtYXV0b3NjYWxpbmcK"
  volumes = [
    {
      delete_with_instance = true
      size                 = 20
      volume_type          = "ESSD_PL0"
    }
  ]
  tags = local.tags
}

resource "volcenginecc_autoscaling_scaling_lifecycle_hook" "scale_out" {
  scaling_group_id       = volcenginecc_autoscaling_scaling_group.app.scaling_group_id
  lifecycle_hook_name    = "${local.prefix}-scale-out"
  lifecycle_hook_type    = "SCALE_OUT"
  lifecycle_hook_timeout = 30
  lifecycle_hook_policy  = "CONTINUE"
}

resource "volcenginecc_autoscaling_scaling_policy" "scheduled" {
  scaling_group_id    = volcenginecc_autoscaling_scaling_group.app.scaling_group_id
  scaling_policy_name = "${local.prefix}-sched"
  scaling_policy_type = "Scheduled"
  adjustment_type     = "QuantityChangeInCapacity"
  adjustment_value    = 1
  cooldown            = 300
  scheduled_policy = {
    launch_time         = var.scheduled_launch_time
    recurrence_end_time = ""
    recurrence_type     = ""
    recurrence_value    = ""
  }
  is_enabled_policy = false
}

output "scaling_policy_id" {
  value = volcenginecc_autoscaling_scaling_policy.scheduled.scaling_policy_id
}

output "scaling_group_id" {
  value = volcenginecc_autoscaling_scaling_group.app.scaling_group_id
}

output "scaling_configuration_id" {
  value = volcenginecc_autoscaling_scaling_configuration.app.scaling_configuration_id
}

output "lifecycle_hook_id" {
  value = volcenginecc_autoscaling_scaling_lifecycle_hook.scale_out.lifecycle_hook_id
}
