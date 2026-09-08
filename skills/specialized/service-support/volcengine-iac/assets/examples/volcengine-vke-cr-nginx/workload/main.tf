terraform {
  required_version = ">= 1.5"

  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.35"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

variable "kubeconfig_path" {
  type        = string
  description = "Path to decoded kubeconfig."
}

variable "registry_endpoint" {
  type        = string
  description = "CR registry endpoint."
}

variable "repository_uri" {
  type        = string
  description = "CR repository URI without tag."
}

variable "cr_username" {
  type        = string
  description = "CR authorization username used only for pushing the image."
}

variable "cr_token" {
  type        = string
  description = "CR authorization token used only for pushing the image."
  sensitive   = true
}

variable "image_tag" {
  type        = string
  description = "Image tag to push and deploy."
  default     = "official-nginx-1.27-amd64"
}

variable "image_platform" {
  type        = string
  description = "Required platform for the VKE ECS nodes used by this example."
  default     = "linux/amd64"

  validation {
    condition     = var.image_platform == "linux/amd64"
    error_message = "This VKE nginx example is verified only on linux/amd64 ECS nodes; keep image_platform set to linux/amd64."
  }
}

variable "use_explicit_image_pull_secret" {
  type        = bool
  description = "Use the verified explicit pull secret path. Set false only after verifying cr-credential-controller injection in your cluster."
  default     = true
}

variable "service_type" {
  type        = string
  description = "Kubernetes Service type. Use LoadBalancer when a public address is required for manual verification."
  default     = "ClusterIP"

  validation {
    condition     = contains(["ClusterIP", "LoadBalancer"], var.service_type)
    error_message = "service_type must be ClusterIP or LoadBalancer."
  }
}

locals {
  namespace_name = "iac-nginx"
  source_image   = "nginx:1.27-alpine"
  target_image   = "${var.repository_uri}:${var.image_tag}"
  dockerconfigjson = jsonencode({
    auths = {
      (var.registry_endpoint) = {
        username = var.cr_username
        password = var.cr_token
        auth     = base64encode("${var.cr_username}:${var.cr_token}")
      }
    }
  })
}

provider "kubernetes" {
  config_path = var.kubeconfig_path
}

resource "null_resource" "nginx_image" {
  triggers = {
    source_image   = local.source_image
    target_image   = local.target_image
    image_platform = var.image_platform
  }

  provisioner "local-exec" {
    interpreter = ["/bin/sh", "-c"]
    environment = {
      CR_TOKEN          = var.cr_token
      CR_USERNAME       = var.cr_username
      IMAGE_PLATFORM    = var.image_platform
      REGISTRY_ENDPOINT = var.registry_endpoint
      SOURCE_IMAGE      = local.source_image
      TARGET_IMAGE      = local.target_image
    }

    command = <<EOT
set -eu
docker image rm "$TARGET_IMAGE" >/dev/null 2>&1 || true
docker image rm "$SOURCE_IMAGE" >/dev/null 2>&1 || true
printf '%s' "$CR_TOKEN" | docker login "$REGISTRY_ENDPOINT" --username "$CR_USERNAME" --password-stdin >/dev/null
docker pull --platform "$IMAGE_PLATFORM" "$SOURCE_IMAGE"
actual_platform="$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$SOURCE_IMAGE")"
if [ "$actual_platform" != "$IMAGE_PLATFORM" ]; then
  echo "Expected $SOURCE_IMAGE to be $IMAGE_PLATFORM, got $actual_platform" >&2
  exit 1
fi
docker tag "$SOURCE_IMAGE" "$TARGET_IMAGE"
docker push "$TARGET_IMAGE"
EOT
  }
}

resource "kubernetes_namespace" "demo" {
  metadata {
    name = local.namespace_name
  }
}

resource "kubernetes_secret" "cr" {
  count = var.use_explicit_image_pull_secret ? 1 : 0

  metadata {
    name      = "volcengine-cr-credential"
    namespace = kubernetes_namespace.demo.metadata[0].name
  }

  type = "kubernetes.io/dockerconfigjson"

  data = {
    ".dockerconfigjson" = local.dockerconfigjson
  }
}

resource "kubernetes_deployment" "nginx" {
  metadata {
    name      = "nginx"
    namespace = kubernetes_namespace.demo.metadata[0].name
    labels = {
      app = "nginx"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "nginx"
      }
    }

    template {
      metadata {
        labels = {
          app = "nginx"
        }
      }

      spec {
        dynamic "image_pull_secrets" {
          for_each = var.use_explicit_image_pull_secret ? [1] : []
          content {
            name = kubernetes_secret.cr[0].metadata[0].name
          }
        }

        container {
          name              = "nginx"
          image             = null_resource.nginx_image.triggers.target_image
          image_pull_policy = "Always"

          port {
            container_port = 80
          }

          resources {
            requests = {
              cpu    = "50m"
              memory = "64Mi"
            }
            limits = {
              cpu    = "250m"
              memory = "128Mi"
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "nginx" {
  metadata {
    name      = "nginx"
    namespace = kubernetes_namespace.demo.metadata[0].name
  }

  spec {
    selector = {
      app = "nginx"
    }

    port {
      port        = 80
      target_port = 80
    }

    type = var.service_type
  }
}

output "image" {
  value = null_resource.nginx_image.triggers.target_image
}

output "namespace" {
  value = kubernetes_namespace.demo.metadata[0].name
}

output "service_type" {
  value = kubernetes_service.nginx.spec[0].type
}
