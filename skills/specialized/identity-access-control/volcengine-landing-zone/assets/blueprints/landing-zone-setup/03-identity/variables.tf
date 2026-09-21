variable "region" {
  description = "火山引擎主 Region"
  type        = string
  default     = "cn-beijing"
}

variable "landing_zone_context_path" {
  description = "Absolute path to the filtered landing-zone-context.json produced from Phase 01 outputs"
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.landing_zone_context_path == null || trimspace(var.landing_zone_context_path) != ""
    error_message = "landing_zone_context_path must be non-empty when provided."
  }
}

variable "prefix" {
  description = "企业名称前缀"
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9-]+$", var.prefix)) && length(var.prefix) >= 2 && length(var.prefix) <= 12
    error_message = "prefix must be 2-12 characters long and contain only letters, numbers, or hyphens."
  }
}

variable "admin_username" {
  description = "管理员用户名"
  type        = string
}

variable "admin_display_name" {
  description = "管理员显示名称"
  type        = string
  default     = "LZ Administrator"
}

variable "admin_email" {
  description = "管理员邮箱，可选"
  type        = string
  default     = null
  nullable    = true
}

variable "session_duration" {
  description = "Permission Set 会话有效期（秒）"
  type        = number
  default     = 3600
}

variable "core_account_ids" {
  description = "Deprecated compatibility input for target account IDs. Prefer landing_zone_context_path."
  type        = list(string)
  default     = null
  nullable    = true
}

variable "management_account_id" {
  description = "Deprecated compatibility input for the management account ID. Prefer landing_zone_context_path."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.management_account_id == null || trimspace(var.management_account_id) != ""
    error_message = "management_account_id must be non-empty when provided."
  }
}
