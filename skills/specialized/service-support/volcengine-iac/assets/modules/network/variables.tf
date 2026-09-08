variable "project" {
  type        = string
  description = "Project name; used as prefix for all resource names"
}

variable "az_primary" {
  type        = string
  description = "Primary availability zone, e.g. cn-beijing-a"
}

variable "az_secondary" {
  type        = string
  description = "Secondary availability zone for HA, e.g. cn-beijing-b"
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR block"
  default     = "10.0.0.0/16"
}

variable "subnet_cidr_primary" {
  type        = string
  description = "Primary subnet CIDR"
  default     = "10.0.1.0/24"
}

variable "subnet_cidr_secondary" {
  type        = string
  description = "Secondary subnet CIDR"
  default     = "10.0.2.0/24"
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to all resources"
  default     = {}
}
