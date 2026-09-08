variable "region" {
  description = "火山引擎主 Region"
  type        = string
  default     = "cn-beijing"
}

variable "prefix" {
  description = "企业名称前缀"
  type        = string
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
  description = "额外目标账号 ID 列表；默认可复用核心账号，也可追加客户已有账号"
  type        = list(string)
}

variable "management_account_id" {
  description = "当前管理账号 ID，会默认并入 AdministratorAccess 的授权目标"
  type        = string

  validation {
    condition     = trimspace(var.management_account_id) != ""
    error_message = "management_account_id 不能为空。"
  }
}
