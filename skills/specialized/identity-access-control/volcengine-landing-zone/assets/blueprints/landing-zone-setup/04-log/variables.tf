variable "region" {
  description = "火山引擎主 Region"
  type        = string
  default     = "cn-beijing"
}

variable "prefix" {
  description = "企业名称前缀"
  type        = string
}

variable "log_archive_account_id" {
  description = "日志归档账号 ID（来自阶段 1 输出）"
  type        = string
}

variable "trail_event_sources" {
  description = "操作审计跟踪的事件源列表。未显式提供时，默认使用 default-trail-event-sources.json 中维护的全量事件源清单。"
  type        = list(string)
  default     = null

  validation {
    condition     = var.trail_event_sources == null || length(var.trail_event_sources) > 0
    error_message = "如果显式提供 trail_event_sources，则其不能为空。"
  }
}
