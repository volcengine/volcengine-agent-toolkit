terraform {
  required_version = ">= 1.5"
  required_providers {
    volcengine = {
      source  = "volcengine/volcengine"
      version = "~> 0.0.196"
    }
  }
}

resource "volcengine_vke_cluster" "main" {
  name                      = "${var.project}-cluster"
  description               = "Managed by volcengine-iac for project ${var.project}"
  kubernetes_version        = var.k8s_version
  delete_protection_enabled = false

  cluster_config {
    subnet_ids                       = var.subnet_ids
    api_server_public_access_enabled = var.enable_public_api

    dynamic "api_server_public_access_config" {
      for_each = var.enable_public_api ? [1] : []
      content {
        public_access_network_config {
          billing_type = "PostPaidByBandwidth"
          bandwidth    = 5
        }
      }
    }

    resource_public_access_default_enabled = false
  }

  pods_config {
    pod_network_mode = "VpcCniShared"

    vpc_cni_config {
      subnet_ids = var.subnet_ids
    }
  }

  services_config {
    service_cidrsv4 = [var.service_cidr]
  }

  dynamic "tags" {
    for_each = var.tags
    content {
      key   = tags.key
      value = tags.value
    }
  }
}

resource "volcengine_vke_node_pool" "main" {
  cluster_id = volcengine_vke_cluster.main.id
  name       = "${var.project}-default-pool"

  auto_scaling {
    enabled          = true
    min_replicas     = var.node_count_min
    max_replicas     = var.node_count_max
    desired_replicas = var.node_count_desired
  }

  node_config {
    instance_type_ids = [var.node_instance_type]
    subnet_ids        = var.subnet_ids

    security {
      security_group_ids  = [var.security_group_id]
      security_strategies = ["Hids"]
    }

    system_volume {
      type = "ESSD_PL0"
      size = var.node_system_volume_size
    }
  }

  kubernetes_config {
    cordon = false
    labels {
      key   = "managed-by"
      value = "volcengine-iac"
    }
  }
}

resource "volcengine_vke_addon" "core_dns" {
  cluster_id = volcengine_vke_cluster.main.id
  name       = "core-dns"
  depends_on = [volcengine_vke_node_pool.main]
}

resource "volcengine_vke_addon" "metrics_server" {
  cluster_id = volcengine_vke_cluster.main.id
  name       = "metrics-server"
  depends_on = [volcengine_vke_node_pool.main]
}
