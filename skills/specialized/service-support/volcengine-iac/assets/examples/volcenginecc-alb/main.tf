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
  prefix  = "cc-iac-alb"
  tags = [
    {
      key   = "purpose"
      value = "terraform-volcenginecc-example"
    }
  ]
}

resource "volcenginecc_vpc_vpc" "main" {
  vpc_name     = "${local.prefix}-vpc"
  description  = "volcenginecc ALB example VPC"
  cidr_block   = "10.92.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
  tags         = local.tags
}

resource "volcenginecc_vpc_subnet" "primary" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = "cn-beijing-a"
  subnet_name = "${local.prefix}-subnet-a"
  description = "volcenginecc ALB example subnet a"
  cidr_block  = "10.92.1.0/24"
  tags        = local.tags
}

resource "volcenginecc_vpc_subnet" "secondary" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = "cn-beijing-b"
  subnet_name = "${local.prefix}-subnet-b"
  description = "volcenginecc ALB example subnet b"
  cidr_block  = "10.92.2.0/24"
  tags        = local.tags
}

resource "volcenginecc_vpc_route_table" "primary" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${local.prefix}-rt-a"
  description      = "volcenginecc ALB example route table a"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids       = [volcenginecc_vpc_subnet.primary.subnet_id]
  tags             = local.tags
}

resource "volcenginecc_vpc_route_table" "secondary" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${local.prefix}-rt-b"
  description      = "volcenginecc ALB example route table b"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids       = [volcenginecc_vpc_subnet.secondary.subnet_id]
  tags             = local.tags
}

resource "volcenginecc_alb_load_balancer" "main" {
  type                           = "private"
  address_ip_version             = "IPv4"
  load_balancer_name             = "${local.prefix}-alb"
  description                    = "volcenginecc ALB example"
  vpc_id                         = volcenginecc_vpc_vpc.main.vpc_id
  load_balancer_billing_type     = 1
  delete_protection              = "off"
  project_name                   = local.project
  modification_protection_status = "NonProtection"
  load_balancer_edition          = "Basic"
  waf_protection_enabled         = "off"

  zone_mappings = [
    {
      subnet_id = volcenginecc_vpc_subnet.primary.subnet_id
      zone_id   = "cn-beijing-a"
    },
    {
      subnet_id = volcenginecc_vpc_subnet.secondary.subnet_id
      zone_id   = "cn-beijing-b"
    }
  ]

  depends_on = [
    volcenginecc_vpc_route_table.primary,
    volcenginecc_vpc_route_table.secondary,
  ]
}

resource "volcenginecc_alb_server_group" "main" {
  vpc_id            = volcenginecc_vpc_vpc.main.vpc_id
  server_group_name = "${local.prefix}-sg"
  server_group_type = "ip"
  protocol          = "HTTP"
  scheduler         = "wrr"
  ip_address_type   = "IPv4"
  project_name      = local.project
  description       = "volcenginecc ALB example server group"

  health_check = {
    enabled             = "off"
    port                = 0
    interval            = 2
    timeout             = 2
    healthy_threshold   = 3
    unhealthy_threshold = 3
    protocol            = "HTTP"
    method              = "HEAD"
    http_version        = "HTTP1.0"
    uri                 = "/"
    http_code           = "http_2xx,http_3xx"
  }

  sticky_session_config = {
    sticky_session_enabled = "off"
  }
}

resource "volcenginecc_alb_listener" "http" {
  load_balancer_id = volcenginecc_alb_load_balancer.main.load_balancer_id
  server_group_id  = volcenginecc_alb_server_group.main.server_group_id
  listener_name    = "${local.prefix}-http"
  protocol         = "HTTP"
  port             = 8080
  enabled          = "off"
  acl_status       = "off"
  description      = "volcenginecc ALB example HTTP listener"
}

resource "volcenginecc_alb_rule" "app" {
  listener_id           = volcenginecc_alb_listener.http.listener_id
  domain                = "alb.example.com"
  url                   = "/app"
  server_group_id       = volcenginecc_alb_server_group.main.server_group_id
  rule_action           = ""
  traffic_limit_enabled = "off"
  description           = "volcenginecc ALB example forwarding rule"
}

output "load_balancer_id" {
  value = volcenginecc_alb_load_balancer.main.load_balancer_id
}

output "server_group_id" {
  value = volcenginecc_alb_server_group.main.server_group_id
}

output "listener_id" {
  value = volcenginecc_alb_listener.http.listener_id
}
