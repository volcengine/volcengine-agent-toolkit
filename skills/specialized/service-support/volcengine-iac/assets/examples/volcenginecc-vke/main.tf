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

variable "node_password_base64" {
  type        = string
  sensitive   = true
  description = "Base64-encoded ECS root password required by VKE node pool NodeConfig.Security.Login."
}

locals {
  project = "default"
  prefix  = "cc-iac-vke"
  zone_a  = "cn-beijing-a"
  zone_b  = "cn-beijing-b"
  tags = [
    {
      key   = "purpose"
      value = "terraform-volcenginecc-example"
    }
  ]
}

resource "volcenginecc_vpc_vpc" "main" {
  vpc_name     = "${local.prefix}-vpc"
  description  = "volcenginecc VKE example VPC"
  cidr_block   = "10.93.0.0/16"
  enable_ipv_6 = false
  project_name = local.project
  tags         = local.tags
}

resource "volcenginecc_vpc_subnet" "primary" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = local.zone_a
  subnet_name = "${local.prefix}-subnet-a"
  description = "volcenginecc VKE example primary subnet"
  cidr_block  = "10.93.1.0/24"
  tags        = local.tags
}

resource "volcenginecc_vpc_subnet" "secondary" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = local.zone_b
  subnet_name = "${local.prefix}-subnet-b"
  description = "volcenginecc VKE example secondary subnet"
  cidr_block  = "10.93.2.0/24"
  tags        = local.tags
}

resource "volcenginecc_vpc_route_table" "app" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${local.prefix}-rt"
  description      = "volcenginecc VKE example route table"
  project_name     = local.project
  associate_type   = "Subnet"
  subnet_ids = [
    volcenginecc_vpc_subnet.primary.subnet_id,
    volcenginecc_vpc_subnet.secondary.subnet_id,
  ]
  tags = local.tags
}

resource "volcenginecc_vke_cluster" "main" {
  project_name              = local.project
  name                      = local.prefix
  description               = "volcenginecc VKE example cluster"
  delete_protection_enabled = false
  kubernetes_version_create = "1.30"

  cluster_config = {
    subnet_ids = [
      volcenginecc_vpc_subnet.primary.subnet_id,
      volcenginecc_vpc_subnet.secondary.subnet_id,
    ]
    api_server_public_access_enabled       = false
    resource_public_access_default_enabled = false
  }

  pods_config = {
    pod_network_mode = "Flannel"
    flannel_config = {
      max_pods_per_node = 64
      pod_cidrs         = ["172.20.0.0/16"]
    }
  }

  services_config = {
    service_cidrsv_4 = ["172.21.0.0/20"]
  }

  tags = local.tags

  depends_on = [
    volcenginecc_vpc_route_table.app,
  ]
}

resource "volcenginecc_vke_node_pool" "zero" {
  cluster_id = volcenginecc_vke_cluster.main.cluster_id
  name       = "${local.prefix}-np"

  auto_scaling = {
    enabled          = false
    min_replicas     = 0
    max_replicas     = 1
    desired_replicas = 0
    subnet_policy    = "ZoneBalance"
  }

  node_config = {
    instance_charge_type  = "PostPaid"
    image_id              = "image-yd6lmt386vgqef1r7xpu"
    instance_type_ids     = ["ecs.g4i.large"]
    project_name          = local.project
    public_access_enabled = false
    subnet_ids            = [volcenginecc_vpc_subnet.primary.subnet_id]

    security = {
      login = {
        password = var.node_password_base64
      }
      security_group_ids = tolist(volcenginecc_vke_cluster.main.cluster_config.security_group_ids)
    }

    system_volume = {
      size = 40
      type = "ESSD_PL0"
    }
  }

  tags = local.tags
}

resource "volcenginecc_vke_default_node_pool" "default" {
  cluster_id = volcenginecc_vke_cluster.main.cluster_id

  node_config = {
    security = {
      login = {
        password = var.node_password_base64
      }
      security_group_ids = tolist(volcenginecc_vke_cluster.main.cluster_config.security_group_ids)
    }
  }
}

resource "volcenginecc_vke_addon" "pod_identity_webhook" {
  cluster_id  = volcenginecc_vke_cluster.main.cluster_id
  name        = "pod-identity-webhook"
  version     = "v0.1.1"
  deploy_mode = "Managed"
}

resource "volcenginecc_vke_kubeconfig" "private" {
  cluster_id     = volcenginecc_vke_cluster.main.cluster_id
  type           = "Private"
  valid_duration = 2
}

output "cluster_id" {
  value = volcenginecc_vke_cluster.main.cluster_id
}

output "node_pool_id" {
  value = volcenginecc_vke_node_pool.zero.node_pool_id
}

output "default_node_pool_id" {
  value = volcenginecc_vke_default_node_pool.default.node_pool_id
}

output "addon_id" {
  value = volcenginecc_vke_addon.pod_identity_webhook.id
}

output "kubeconfig_id" {
  value = volcenginecc_vke_kubeconfig.private.kubeconfig_id
}
