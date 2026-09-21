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
  description = "企业名称前缀，与 01-organization 阶段保持一致；仅用于兼容旧 financial_relation_accounts 输入的 alias 拼接。"
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

  validation {
    condition     = contains(["Financial_Hosting", "Financial_Association"], var.financial_relation_type)
    error_message = "financial_relation_type must be Financial_Hosting or Financial_Association."
  }
}

variable "financial_relation_accounts" {
  description = "Deprecated compatibility input: stable account key to account ID. Prefer financial_relation_targets from 01-organization."
  type        = map(string)
  default     = {}
}

variable "financial_relation_targets" {
  description = "Phase 01 finance_relation_targets output: stable account key to explicit account ID and billing alias"
  type = map(object({
    account_id    = string
    account_alias = string
  }))
  default = null

  validation {
    condition = var.financial_relation_targets == null || alltrue([
      for key, target in var.financial_relation_targets : (
        trimspace(key) != "" &&
        trimspace(target.account_id) != "" &&
        can(regex("^[A-Za-z0-9._-]+$", target.account_alias))
      )
    ])
    error_message = "financial_relation_targets keys and account IDs must be non-empty, and aliases may use only letters, numbers, dots, underscores, or hyphens."
  }
}

variable "financial_relation_auth_list_str" {
  description = "可选授权列表，多个权限点以逗号分隔；为空时表示不附带授权列表"
  type        = string
  default     = ""
}
