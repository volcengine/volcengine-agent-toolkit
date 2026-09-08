variable "region" {
  description = "火山引擎主 Region"
  type        = string
  default     = "cn-beijing"
}

variable "prefix" {
  description = "企业名称前缀，与 01-organization 阶段保持一致；实际 AccountAlias 会按 prefix-<key> 自动拼接，避免与其他执行或已有账号 alias 冲突。"
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9-]+$", var.prefix)) && length(var.prefix) >= 2 && length(var.prefix) <= 12
    error_message = "prefix must be 2-12 characters long and contain only letters, numbers, or hyphens."
  }
}

variable "financial_relation_type" {
  description = "财务关系类型：Financial_Hosting(财务托管) 或 Financial_Association(财务关联)"
  type        = string
  default     = "Financial_Hosting"
}

variable "financial_relation_accounts" {
  description = "需要建立财务关系的子账号 ID 映射，key 为账号别名，value 为账号 ID"
  type        = map(string)
}

variable "financial_relation_auth_list_str" {
  description = "可选授权列表，多个权限点以逗号分隔；为空时表示不附带授权列表"
  type        = string
  default     = ""
}
