variable "region" {
  description = "火山引擎主 Region"
  type        = string
  default     = "cn-beijing"
}

variable "prefix" {
  description = "企业名称前缀，用于账号命名"
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9-]+$", var.prefix)) && length(var.prefix) >= 2 && length(var.prefix) <= 12
    error_message = "prefix must be 2-12 characters long and contain only letters, numbers, or hyphens."
  }
}

variable "root_ou_id" {
  description = "Root OU ID (from `ve organization ListOrganizationalUnits --body '{}'`, where Name=`Root` and Depth=`0`)"
  type        = string
}

variable "existing_platform_ou_id" {
  description = "可选，已存在的 Platform OU ID；提供后将直接复用，不再重复创建。标准流程下建议由 skill 在执行前自动扫描现有 OU 并注入。"
  type        = string
  default     = null
}

variable "existing_applications_ou_id" {
  description = "可选，已存在的 Applications OU ID；提供后将直接复用，不再重复创建。标准流程下建议由 skill 在执行前自动扫描现有 OU 并注入。"
  type        = string
  default     = null
}

variable "existing_sandbox_ou_id" {
  description = "可选，已存在的 SandBox OU ID；提供后将直接复用，不再重复创建。标准流程下建议由 skill 在执行前自动扫描现有 OU 并注入。"
  type        = string
  default     = null
}

variable "existing_applications_dev_ou_id" {
  description = "可选，已存在的 Applications/Dev OU ID；提供后将直接复用，不再重复创建。标准流程下建议由 skill 在执行前自动扫描现有 OU 并注入。"
  type        = string
  default     = null
}

variable "existing_applications_staging_ou_id" {
  description = "可选，已存在的 Applications/Staging OU ID；提供后将直接复用，不再重复创建。标准流程下建议由 skill 在执行前自动扫描现有 OU 并注入。"
  type        = string
  default     = null
}

variable "existing_applications_prod_ou_id" {
  description = "可选，已存在的 Applications/Prod OU ID；提供后将直接复用，不再重复创建。标准流程下建议由 skill 在执行前自动扫描现有 OU 并注入。"
  type        = string
  default     = null
}
