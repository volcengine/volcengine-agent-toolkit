variable "region" {
  description = "火山引擎主 Region"
  type        = string
  default     = "cn-beijing"
}

variable "account_name" {
  description = "待创建账号的登录名/唯一账号名"
  type        = string
}

variable "show_name" {
  description = "待创建账号的展示名称"
  type        = string
}

variable "target_ou_id" {
  description = "目标 OU ID，账号创建后将放置在该 OU 下"
  type        = string
}

variable "account_tags" {
  description = "账号标签列表"
  type = list(object({
    key   = string
    value = string
  }))
  default = []
}

variable "financial_relation_type" {
  description = "财务关系类型：Financial_Hosting 或 Financial_Association"
  type        = string
}

variable "financial_relation_auth_list_str" {
  description = "可选授权列表，多个权限点以逗号分隔；为空时表示不附带授权列表"
  type        = string
  default     = ""
}

variable "financial_relation_account_alias" {
  description = "可选财务关系账号别名；为空时默认使用 account_name，若自动生成的别名冲突会追加账号 ID 后缀重试一次"
  type        = string
  default     = ""
}
