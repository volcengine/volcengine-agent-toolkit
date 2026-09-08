variable "project" {
  type        = string
  description = "Project name; used as instance name prefix"
}

variable "subnet_id" {
  type        = string
  description = "Subnet ID (primary AZ); from network module"
}

variable "primary_zone_id" {
  type        = string
  description = "Primary availability zone (e.g. cn-beijing-a)"
}

variable "secondary_zone_id" {
  type        = string
  description = "Secondary availability zone for HA replica (e.g. cn-beijing-b)"
}

variable "db_engine_version" {
  type        = string
  description = "MySQL engine version: MySQL_5_7 or MySQL_8_0"
  default     = "MySQL_8_0"
  validation {
    condition     = contains(["MySQL_5_7", "MySQL_8_0"], var.db_engine_version)
    error_message = "db_engine_version must be MySQL_5_7 or MySQL_8_0."
  }
}

variable "instance_type" {
  type        = string
  description = "Node spec name (e.g. rds.mysql.1c2g)"
  default     = "rds.mysql.1c2g"
}

variable "storage_space" {
  type        = number
  description = "Storage size in GB"
  default     = 100
}

variable "charge_type" {
  type        = string
  description = "Billing model: PostPaid or PrePaid"
  default     = "PostPaid"
  validation {
    condition     = contains(["PostPaid", "PrePaid"], var.charge_type)
    error_message = "charge_type must be PostPaid or PrePaid."
  }
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to the instance"
  default     = {}
}
