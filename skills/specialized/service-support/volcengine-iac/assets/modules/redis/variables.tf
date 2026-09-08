variable "project" {
  type        = string
  description = "Project name; used as instance name prefix"
}

variable "subnet_id" {
  type        = string
  description = "Subnet ID where the Redis instance is deployed"
}

variable "primary_az" {
  type        = string
  description = "Primary AZ for the Redis instance (e.g. cn-beijing-a)"
}

variable "secondary_az" {
  type        = string
  description = "Secondary AZ; used only when multi_az=enabled"
  default     = ""
}

variable "engine_version" {
  type        = string
  description = "Redis engine version: 5.0, 6.0, or 7.0"
  default     = "6.0"
  validation {
    condition     = contains(["5.0", "6.0", "7.0"], var.engine_version)
    error_message = "engine_version must be 5.0, 6.0, or 7.0."
  }
}

variable "node_number" {
  type        = number
  description = "Nodes per shard (1 for single-node, 2 for primary+replica HA)"
  default     = 2
  validation {
    condition     = var.node_number >= 1 && var.node_number <= 6
    error_message = "node_number must be between 1 and 6."
  }
}

variable "shard_capacity" {
  type        = number
  description = "Memory per shard in MiB (e.g. 1024 for 1GB; check console for allowed values)"
  default     = 1024
}

variable "sharded_cluster" {
  type        = number
  description = "Sharded cluster mode: 0=disabled, 1=enabled"
  default     = 0
  validation {
    condition     = contains([0, 1], var.sharded_cluster)
    error_message = "sharded_cluster must be 0 or 1."
  }
}

variable "multi_az" {
  type        = string
  description = "Multi-AZ deployment: disabled or enabled"
  default     = "disabled"
  validation {
    condition     = contains(["disabled", "enabled"], var.multi_az)
    error_message = "multi_az must be disabled or enabled."
  }
}

variable "port" {
  type        = number
  description = "Redis listening port (1024-65535)"
  default     = 6379
}

variable "charge_type" {
  type        = string
  description = "Billing model: PostPaid or PrePaid"
  default     = "PostPaid"
}

variable "tags" {
  type        = map(string)
  description = "Tags"
  default     = {}
}
