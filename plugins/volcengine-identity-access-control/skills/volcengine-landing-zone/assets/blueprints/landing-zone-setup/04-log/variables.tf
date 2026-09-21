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

variable "log_archive_account_id" {
  description = "Deprecated compatibility input for the log archive account ID. Prefer landing_zone_context_path."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.log_archive_account_id == null || trimspace(var.log_archive_account_id) != ""
    error_message = "log_archive_account_id must be non-empty when provided."
  }
}

variable "trail_event_sources" {
  description = "操作审计跟踪的事件源列表。未显式提供时，默认通过 CreateTrail 的 IncludeAllEventSources=true 采集全部事件源；仅当需要收窄审计范围时才传入具体事件源。"
  type        = list(string)
  default     = null

  validation {
    condition     = var.trail_event_sources == null || length(var.trail_event_sources) > 0
    error_message = "如果显式提供 trail_event_sources，则其不能为空。"
  }
}
