variable "project" {
  type        = string
  description = "Project name; used as cluster name prefix"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID from network module"
}

variable "subnet_ids" {
  type        = list(string)
  description = "Subnet IDs (typically 2 across AZs) for cluster API server and node pool placement"
  validation {
    condition     = length(var.subnet_ids) >= 1 && length(var.subnet_ids) <= 3
    error_message = "Provide 1–3 subnet IDs."
  }
}

variable "security_group_id" {
  type        = string
  description = "Security group ID for the node pool"
}

variable "k8s_version" {
  type        = string
  description = "Kubernetes version (e.g. 1.30)"
  default     = "1.30"
}

variable "service_cidr" {
  type        = string
  description = "Service CIDR for in-cluster services (avoid VPC overlap)"
  default     = "192.168.0.0/16"
}

variable "node_instance_type" {
  type        = string
  description = "Instance type for worker nodes (run `ve ecs DescribeAvailableResource` to verify availability)"
  default     = "ecs.g3i.xlarge"
}

variable "node_count_desired" {
  type        = number
  description = "Desired worker node count"
  default     = 2
}

variable "node_count_min" {
  type        = number
  description = "Autoscaling minimum"
  default     = 1
}

variable "node_count_max" {
  type        = number
  description = "Autoscaling maximum"
  default     = 5
}

variable "node_system_volume_size" {
  type        = number
  description = "System disk size in GB per node"
  default     = 50
}

variable "enable_public_api" {
  type        = bool
  description = "Whether to expose the kube-apiserver publicly (requires extra cost via PostPaidByBandwidth)"
  default     = false
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to the cluster"
  default     = {}
}
