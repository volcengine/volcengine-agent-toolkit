variable "region" {
  description = "火山引擎主 Region"
  type        = string
  default     = "cn-beijing"
}

variable "prefix" {
  description = "企业名称前缀；默认架构使用它生成账号名称，自定义架构仍保留该值供后续阶段命名"
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9-]+$", var.prefix)) && length(var.prefix) >= 2 && length(var.prefix) <= 12
    error_message = "prefix must be 2-12 characters long and contain only letters, numbers, or hyphens."
  }
}

variable "configuration_schema_version" {
  description = "confirmed-architecture.json schema version"
  type        = number
  default     = 1

  validation {
    condition     = var.configuration_schema_version == 1
    error_message = "configuration_schema_version must be 1."
  }
}

variable "architecture_profile" {
  description = "Versioned recommended architecture used as the base of the confirmed design"
  type        = string
  default     = "recommended-v1"

  validation {
    condition     = var.architecture_profile == "recommended-v1"
    error_message = "architecture_profile must be recommended-v1."
  }
}

variable "architecture_mode" {
  description = "Confirmed design mode. Leave null only for legacy callers; the standard skill path sets default or custom explicitly."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.architecture_mode == null || contains(["default", "custom"], var.architecture_mode)
    error_message = "architecture_mode must be default, custom, or null for legacy callers."
  }
}

variable "confirmed_architecture_sha256" {
  description = "SHA-256 digest of the exact confirmed-architecture.json bytes. Leave null only for legacy callers."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.confirmed_architecture_sha256 == null || can(regex("^[a-f0-9]{64}$", var.confirmed_architecture_sha256))
    error_message = "confirmed_architecture_sha256 must be a lowercase 64-character SHA-256 digest."
  }
}

variable "enabled_capabilities" {
  description = "Landing Zone phases enabled by the confirmed design. Null preserves legacy callers by deriving capabilities from selectors and role bindings."
  type = object({
    finance  = bool
    identity = bool
    log      = bool
    network  = bool
  })
  default  = null
  nullable = true
}

variable "management_account_id" {
  description = "Verified organization management account ID used to bind downstream execution context"
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.management_account_id == null || trimspace(var.management_account_id) != ""
    error_message = "management_account_id must be non-empty when provided."
  }
}

variable "organization_id" {
  description = "Enterprise organization ID when exposed by discovery; optional because some CLI responses only expose Root OU"
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.organization_id == null || trimspace(var.organization_id) != ""
    error_message = "organization_id must be non-empty when provided."
  }
}

variable "root_ou_id" {
  description = "Root OU ID (resolved from the current enterprise organization before plan)"
  type        = string

  validation {
    condition     = trimspace(var.root_ou_id) != ""
    error_message = "root_ou_id must not be empty."
  }
}

variable "organization_architecture" {
  description = <<-EOT
    Complete desired OU/account architecture. Leave null to use the recommended
    default architecture. Stable map keys identify objects; display names may be
    changed independently. OU level must be 1-5 and parent_key must identify an
    OU exactly one level above. An account with ou_key=null is placed at Root.
  EOT

  type = object({
    ous = map(object({
      name        = string
      parent_key  = optional(string)
      level       = number
      description = optional(string)
    }))
    accounts = map(object({
      account_name             = string
      show_name                = string
      ou_key                   = optional(string)
      description              = optional(string)
      financial_account_alias  = optional(string)
      finance_enabled          = optional(bool, true)
      identity_enabled         = optional(bool, true)
      allow_console            = optional(number)
      allow_exit               = optional(number)
      verification_relation_id = optional(string)
      tags                     = optional(map(string), {})
    }))
    role_account_keys = map(string)
  })
  default = null

  validation {
    condition = var.organization_architecture == null || (
      length(var.organization_architecture.ous) <= 20 &&
      alltrue([
        for key, ou in var.organization_architecture.ous : (
          can(regex("^[a-z][a-z0-9_-]{0,63}$", key)) &&
          trimspace(ou.name) != "" &&
          ou.level >= 1 && ou.level <= 5
        )
      ])
    )
    error_message = "OU keys must be stable lowercase identifiers, names must be non-empty, the OU count must not exceed 20, and levels must be between 1 and 5."
  }

  validation {
    condition = var.organization_architecture == null || alltrue([
      for key, ou in var.organization_architecture.ous : ou.level == 1 ? ou.parent_key == null : (
        ou.parent_key != null &&
        try(var.organization_architecture.ous[ou.parent_key].level == ou.level - 1, false)
      )
    ])
    error_message = "Each level-1 OU must use Root, and every deeper OU must reference a declared OU exactly one level above it."
  }

  validation {
    condition = var.organization_architecture == null || (
      length(distinct([
        for key, ou in var.organization_architecture.ous : "${coalesce(ou.parent_key, "__root__")}/${lower(trimspace(ou.name))}"
      ])) == length(var.organization_architecture.ous)
    )
    error_message = "Sibling OU names must be unique (case-insensitive)."
  }

  validation {
    condition = var.organization_architecture == null || (
      length(var.organization_architecture.accounts) <= 20 &&
      alltrue([
        for key, account in var.organization_architecture.accounts : (
          can(regex("^[a-z][a-z0-9_-]{0,63}$", key)) &&
          length(account.account_name) >= 5 && length(account.account_name) <= 20 &&
          trimspace(account.show_name) != "" &&
          (account.ou_key == null || contains(keys(var.organization_architecture.ous), account.ou_key)) &&
          (account.allow_console == null || contains([1, 2], account.allow_console)) &&
          (account.allow_exit == null || contains([1, 2], account.allow_exit))
        )
      ])
    )
    error_message = "Account keys must be stable lowercase identifiers, account_name must be 5-20 characters, show_name must be non-empty, ou_key must exist, and allow_console/allow_exit must be 1 or 2 when set."
  }

  validation {
    condition = var.organization_architecture == null || (
      length(distinct([
        for key, account in var.organization_architecture.accounts : lower(account.account_name)
      ])) == length(var.organization_architecture.accounts) &&
      alltrue([
        for role, account_key in var.organization_architecture.role_account_keys : (
          trimspace(role) != "" && contains(keys(var.organization_architecture.accounts), account_key)
        )
      ])
    )
    error_message = "Account names must be unique (case-insensitive), and every semantic role must reference a declared account key."
  }

  validation {
    condition = var.organization_architecture == null || (
      alltrue([
        for key, account in var.organization_architecture.accounts : (
          account.financial_account_alias == null ||
          can(regex("^[A-Za-z0-9._-]+$", account.financial_account_alias))
        )
      ]) &&
      length(distinct([
        for key, account in var.organization_architecture.accounts : lower(
          account.financial_account_alias == null ? account.account_name : account.financial_account_alias
        ) if account.finance_enabled
        ])) == length([
        for key, account in var.organization_architecture.accounts : key if account.finance_enabled
      ])
    )
    error_message = "Finance aliases must use only letters, numbers, dots, underscores, or hyphens, and finance-enabled aliases must be unique (case-insensitive)."
  }

}

variable "existing_ou_ids" {
  description = "Read-only discovery result: stable OU key to existing OU ID. Matching entries are verified and reused instead of created."
  type        = map(string)
  default     = {}

  validation {
    condition = (
      alltrue([for key, id in var.existing_ou_ids : trimspace(key) != "" && trimspace(id) != ""]) &&
      length(distinct(values(var.existing_ou_ids))) == length(var.existing_ou_ids)
    )
    error_message = "existing_ou_ids must contain non-empty, unique OU IDs."
  }
}

variable "existing_account_ids" {
  description = "Read-only discovery result: stable account key to existing organization account ID. Matching entries are verified and reused instead of created."
  type        = map(string)
  default     = {}

  validation {
    condition = (
      alltrue([for key, id in var.existing_account_ids : trimspace(key) != "" && trimspace(id) != ""]) &&
      length(distinct(values(var.existing_account_ids))) == length(var.existing_account_ids)
    )
    error_message = "existing_account_ids must contain non-empty, unique account IDs."
  }
}

# Deprecated compatibility inputs for workspaces created by earlier versions.
# New discovery flows should populate existing_ou_ids by stable key.
variable "existing_platform_ou_id" {
  description = "Deprecated: use existing_ou_ids.platform."
  type        = string
  default     = null
}

variable "existing_applications_ou_id" {
  description = "Deprecated: use existing_ou_ids.applications."
  type        = string
  default     = null
}

variable "existing_sandbox_ou_id" {
  description = "Deprecated: use existing_ou_ids.sandbox."
  type        = string
  default     = null
}

variable "existing_applications_dev_ou_id" {
  description = "Deprecated: use existing_ou_ids.applications_dev."
  type        = string
  default     = null
}

variable "existing_applications_staging_ou_id" {
  description = "Deprecated: use existing_ou_ids.applications_staging."
  type        = string
  default     = null
}

variable "existing_applications_prod_ou_id" {
  description = "Deprecated: use existing_ou_ids.applications_prod."
  type        = string
  default     = null
}
