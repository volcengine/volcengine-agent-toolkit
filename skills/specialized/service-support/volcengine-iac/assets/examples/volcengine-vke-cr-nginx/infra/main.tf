terraform {
  required_version = ">= 1.5"

  required_providers {
    volcenginecc = {
      source  = "volcengine/volcenginecc"
      version = "~> 0.0.46"
    }
    volcengine = {
      source  = "volcengine/volcengine"
      version = "~> 0.0.196"
    }
  }
}

provider "volcenginecc" {}
provider "volcengine" {}

variable "prefix" {
  type        = string
  description = "Unique lowercase prefix for temporary resources."
  default     = "iac-vke-cr-nginx"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,29}$", var.prefix)) && !endswith(var.prefix, "-")
    error_message = "prefix must be 3-30 chars, start with a letter, contain only lowercase letters, digits, and hyphens, and not end with a hyphen."
  }
}

variable "project" {
  type        = string
  description = "Volcengine project name."
  default     = "default"
}

variable "region" {
  type        = string
  description = "Volcengine region ID."
  default     = "cn-beijing"
}

variable "zone_a" {
  type        = string
  description = "Primary availability zone."
  default     = "cn-beijing-a"
}

variable "zone_b" {
  type        = string
  description = "Secondary availability zone."
  default     = "cn-beijing-b"
}

variable "node_password_base64" {
  type        = string
  description = "Base64-encoded ECS root password required by VKE node pools."
  sensitive   = true
}

variable "kubeconfig_grantee_id" {
  type        = number
  description = "Optional IAM user ID to grant vke:admin before creating a kubeconfig."
  default     = null
}

variable "manage_core_dns_addon" {
  type        = bool
  description = "Whether to create core-dns as a Terraform addon resource. See the reference before destroying when true."
  default     = true
}

locals {
  namespace_name  = "app"
  repository_name = "nginx"
  tags = [
    {
      key   = "purpose"
      value = "iac-vke-cr-nginx"
    },
    {
      key   = "managed-by"
      value = "terraform"
    },
  ]
}

resource "volcenginecc_vpc_vpc" "main" {
  vpc_name     = "${var.prefix}-vpc"
  description  = "VKE CR nginx IaC example VPC"
  cidr_block   = "10.94.0.0/16"
  enable_ipv_6 = false
  project_name = var.project
  tags         = local.tags
}

resource "volcenginecc_vpc_subnet" "primary" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = var.zone_a
  subnet_name = "${var.prefix}-subnet-a"
  description = "VKE CR nginx IaC example primary subnet"
  cidr_block  = "10.94.1.0/24"
  tags        = local.tags
}

resource "volcenginecc_vpc_subnet" "secondary" {
  vpc_id      = volcenginecc_vpc_vpc.main.vpc_id
  zone_id     = var.zone_b
  subnet_name = "${var.prefix}-subnet-b"
  description = "VKE CR nginx IaC example secondary subnet"
  cidr_block  = "10.94.2.0/24"
  tags        = local.tags
}

resource "volcenginecc_vpc_route_table" "app" {
  vpc_id           = volcenginecc_vpc_vpc.main.vpc_id
  route_table_name = "${var.prefix}-rt"
  description      = "VKE CR nginx IaC example route table"
  project_name     = var.project
  associate_type   = "Subnet"
  subnet_ids = [
    volcenginecc_vpc_subnet.primary.subnet_id,
    volcenginecc_vpc_subnet.secondary.subnet_id,
  ]
  tags = local.tags
}

resource "volcengine_cr_registry" "main" {
  name               = var.prefix
  project            = var.project
  type               = "Enterprise"
  delete_immediately = true

  resource_tags {
    key   = "purpose"
    value = "iac-vke-cr-nginx"
  }

  resource_tags {
    key   = "managed-by"
    value = "terraform"
  }
}

resource "volcengine_cr_endpoint" "public" {
  registry = volcengine_cr_registry.main.name
  enabled  = true
}

resource "volcengine_cr_endpoint_acl_policy" "public" {
  registry    = volcengine_cr_registry.main.name
  type        = "Public"
  entry       = "0.0.0.0/0"
  description = "Temporary public CR push/pull ACL for the IaC VKE nginx example"

  depends_on = [
    volcengine_cr_endpoint.public,
  ]
}

resource "volcengine_cr_namespace" "app" {
  registry                        = volcengine_cr_registry.main.name
  name                            = local.namespace_name
  project                         = var.project
  repository_default_access_level = "Private"
}

resource "volcengine_cr_repository" "nginx" {
  registry     = volcengine_cr_registry.main.name
  namespace    = volcengine_cr_namespace.app.name
  name         = local.repository_name
  description  = "Private nginx image repository for VKE pull validation"
  access_level = "Private"
}

data "volcengine_cr_authorization_tokens" "main" {
  registry = volcengine_cr_registry.main.name

  depends_on = [
    volcengine_cr_endpoint_acl_policy.public,
    volcengine_cr_repository.nginx,
  ]
}

resource "volcenginecc_vke_cluster" "main" {
  project_name              = var.project
  name                      = var.prefix
  description               = "VKE cluster for the IaC CR nginx example"
  delete_protection_enabled = false
  kubernetes_version_create = "1.30"

  cluster_config = {
    subnet_ids = [
      volcenginecc_vpc_subnet.primary.subnet_id,
      volcenginecc_vpc_subnet.secondary.subnet_id,
    ]
    api_server_public_access_enabled = true
    api_server_public_access_config = {
      public_access_network_config = {
        billing_type = 3
        bandwidth    = 1
        isp          = "BGP"
      }
    }
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

resource "volcenginecc_vke_node_pool" "main" {
  cluster_id = volcenginecc_vke_cluster.main.cluster_id
  name       = "${var.prefix}-np"

  auto_scaling = {
    enabled          = true
    min_replicas     = 0
    max_replicas     = 1
    desired_replicas = 1
    subnet_policy    = "ZoneBalance"
  }

  node_config = {
    instance_charge_type  = "PostPaid"
    image_id              = "image-yd6lmt386vgqef1r7xpu"
    instance_type_ids     = ["ecs.g4i.large"]
    project_name          = var.project
    public_access_enabled = true
    public_access_config = {
      bandwidth    = 1
      billing_type = 3
      isp          = "BGP"
    }
    subnet_ids = [volcenginecc_vpc_subnet.primary.subnet_id]

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

resource "volcenginecc_vke_node_pool" "dns" {
  cluster_id = volcenginecc_vke_cluster.main.cluster_id
  name       = "${var.prefix}-dns-np"

  auto_scaling = {
    enabled          = true
    min_replicas     = 0
    max_replicas     = 1
    desired_replicas = 1
    subnet_policy    = "ZoneBalance"
  }

  node_config = {
    instance_charge_type  = "PostPaid"
    image_id              = "image-yd6lmt386vgqef1r7xpu"
    instance_type_ids     = ["ecs.g4i.2xlarge"]
    project_name          = var.project
    public_access_enabled = true
    public_access_config = {
      bandwidth    = 1
      billing_type = 3
      isp          = "BGP"
    }
    subnet_ids = [volcenginecc_vpc_subnet.primary.subnet_id]

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

resource "volcengine_vke_permission" "operator" {
  count = var.kubeconfig_grantee_id == null ? 0 : 1

  role_domain  = "cluster"
  cluster_id   = volcenginecc_vke_cluster.main.cluster_id
  role_name    = "vke:admin"
  grantee_id   = var.kubeconfig_grantee_id
  grantee_type = "User"
}

resource "volcenginecc_vke_addon" "core_dns" {
  count = var.manage_core_dns_addon ? 1 : 0

  cluster_id       = volcenginecc_vke_cluster.main.cluster_id
  name             = "core-dns"
  version          = "1.11.3"
  deploy_mode      = "Unmanaged"
  deploy_node_type = "Node"

  depends_on = [
    volcenginecc_vke_node_pool.dns,
  ]
}

resource "volcenginecc_vke_addon" "cr_credential_controller" {
  cluster_id       = volcenginecc_vke_cluster.main.cluster_id
  name             = "cr-credential-controller"
  version          = "v1.3.5"
  deploy_mode      = "Unmanaged"
  deploy_node_type = "Node"
  config = jsonencode({
    CrConfigmapData = {
      Namespace      = "*"
      ServiceAccount = "*"
      Registries = [
        {
          Instance = volcengine_cr_registry.main.name
          Region   = var.region
          Domains  = [local.registry_endpoint]
        }
      ]
    }
  })

  depends_on = [
    volcenginecc_vke_node_pool.dns,
    volcengine_cr_repository.nginx,
  ]
}

resource "volcengine_vke_kubeconfig" "public" {
  cluster_id     = volcenginecc_vke_cluster.main.cluster_id
  type           = "Public"
  valid_duration = 1

  depends_on = [
    volcenginecc_vke_node_pool.dns,
    volcengine_vke_permission.operator,
  ]
}

data "volcengine_vke_kubeconfigs" "public" {
  ids = [volcengine_vke_kubeconfig.public.id]
}

locals {
  registry_endpoint = volcengine_cr_registry.main.domains[0].domain
  repository_uri    = "${local.registry_endpoint}/${volcengine_cr_namespace.app.name}/${volcengine_cr_repository.nginx.name}"
  cr_token          = tolist(data.volcengine_cr_authorization_tokens.main.tokens)[0]
}

output "cluster_id" {
  value = volcenginecc_vke_cluster.main.cluster_id
}

output "kubeconfig" {
  value     = data.volcengine_vke_kubeconfigs.public.kubeconfigs[0].kubeconfig
  sensitive = true
}

output "registry_name" {
  value = volcengine_cr_registry.main.name
}

output "registry_endpoint" {
  value = local.registry_endpoint
}

output "repository_uri" {
  value = local.repository_uri
}

output "cr_username" {
  value = local.cr_token.username
}

output "cr_token" {
  value     = local.cr_token.token
  sensitive = true
}
