terraform {
  required_version = ">= 1.5.0"

  required_providers {
    volcenginecc = {
      source  = "volcengine/volcenginecc"
      version = "0.0.69"
    }
  }
}

provider "volcenginecc" {
  region = var.region
}

locals {
  # `organization_architecture = null` remains a legacy compatibility path.
  # The standard skill flow materializes this recommended-v1 design into the
  # confirmed architecture snapshot and passes the complete object explicitly.
  # Stable keys are deliberately separate from display names so customers can
  # rename an OU/account without breaking downstream semantic role lookups.
  recommended_v1_organization_architecture = {
    ous = {
      platform = {
        name        = "Platform"
        parent_key  = null
        level       = 1
        description = "Landing Zone governance accounts"
      }
      applications = {
        name        = "Applications"
        parent_key  = null
        level       = 1
        description = "Application workload accounts"
      }
      sandbox = {
        name        = "SandBox"
        parent_key  = null
        level       = 1
        description = "Sandbox and proof-of-concept accounts"
      }
      applications_dev = {
        name        = "Dev"
        parent_key  = "applications"
        level       = 2
        description = "Development workload accounts"
      }
      applications_staging = {
        name        = "Staging"
        parent_key  = "applications"
        level       = 2
        description = "Staging workload accounts"
      }
      applications_prod = {
        name        = "Prod"
        parent_key  = "applications"
        level       = 2
        description = "Production workload accounts"
      }
    }
    accounts = {
      log_archive = {
        account_name             = "${var.prefix}-Log"
        show_name                = "${var.prefix}-LogArchiveAccount"
        ou_key                   = "platform"
        description              = "Landing Zone log archive account"
        financial_account_alias  = "${var.prefix}-log_archive"
        finance_enabled          = true
        identity_enabled         = true
        allow_console            = null
        allow_exit               = null
        verification_relation_id = null
        tags                     = {}
      }
      security = {
        account_name             = "${var.prefix}-Sec"
        show_name                = "${var.prefix}-SecurityAccount"
        ou_key                   = "platform"
        description              = "Landing Zone security account"
        financial_account_alias  = "${var.prefix}-security"
        finance_enabled          = true
        identity_enabled         = true
        allow_console            = null
        allow_exit               = null
        verification_relation_id = null
        tags                     = {}
      }
      shared_service = {
        account_name             = "${var.prefix}-Shared"
        show_name                = "${var.prefix}-SharedServiceAccount"
        ou_key                   = "platform"
        description              = "Landing Zone shared services account"
        financial_account_alias  = "${var.prefix}-shared_service"
        finance_enabled          = true
        identity_enabled         = true
        allow_console            = null
        allow_exit               = null
        verification_relation_id = null
        tags                     = {}
      }
      network = {
        account_name             = "${var.prefix}-Net"
        show_name                = "${var.prefix}-NetworkAccount"
        ou_key                   = "platform"
        description              = "Landing Zone network account"
        financial_account_alias  = "${var.prefix}-network"
        finance_enabled          = true
        identity_enabled         = true
        allow_console            = null
        allow_exit               = null
        verification_relation_id = null
        tags                     = {}
      }
      sandbox_test = {
        account_name             = "${var.prefix}-SandBox"
        show_name                = "${var.prefix}-SandBoxTestAccount"
        ou_key                   = "sandbox"
        description              = "Landing Zone sandbox test account"
        financial_account_alias  = "${var.prefix}-sandbox_test"
        finance_enabled          = true
        identity_enabled         = true
        allow_console            = null
        allow_exit               = null
        verification_relation_id = null
        tags                     = {}
      }
    }
    role_account_keys = {
      log_archive    = "log_archive"
      security       = "security"
      shared_service = "shared_service"
      network        = "network"
      sandbox_test   = "sandbox_test"
    }
  }

  architecture = var.organization_architecture == null ? local.recommended_v1_organization_architecture : var.organization_architecture
  ous          = local.architecture.ous
  accounts     = local.architecture.accounts
  roles        = local.architecture.role_account_keys
  effective_capabilities = var.enabled_capabilities != null ? var.enabled_capabilities : {
    finance  = length([for key, account in local.accounts : key if account.finance_enabled]) > 0
    identity = length([for key, account in local.accounts : key if account.identity_enabled]) > 0
    log      = contains(keys(local.roles), "log_archive")
    network  = contains(keys(local.roles), "network")
  }

  effective_architecture_mode = coalesce(
    var.architecture_mode,
    var.organization_architecture == null ? "default" : "custom",
  )
  effective_architecture_sha256 = coalesce(
    var.confirmed_architecture_sha256,
    sha256(jsonencode({
      schema_version = var.configuration_schema_version
      profile = {
        mode = local.effective_architecture_mode
        base = var.architecture_profile
      }
      settings = {
        prefix = var.prefix
        region = var.region
      }
      capabilities              = local.effective_capabilities
      organization_architecture = local.architecture
    })),
  )

  # Backward-compatible inputs for the original default OU layout are merged
  # with the generic discovery result. Generic keys win when both are set.
  legacy_existing_ou_ids = {
    for key, id in {
      platform             = var.existing_platform_ou_id
      applications         = var.existing_applications_ou_id
      sandbox              = var.existing_sandbox_ou_id
      applications_dev     = var.existing_applications_dev_ou_id
      applications_staging = var.existing_applications_staging_ou_id
      applications_prod    = var.existing_applications_prod_ou_id
    } : key => id if id != null
  }
  requested_existing_ou_ids      = merge(local.legacy_existing_ou_ids, var.existing_ou_ids)
  requested_existing_account_ids = var.existing_account_ids
  existing_ou_ids = {
    for key, id in local.requested_existing_ou_ids : key => id
    if contains(keys(local.ous), key)
  }
  existing_account_ids = {
    for key, id in local.requested_existing_account_ids : key => id
    if contains(keys(local.accounts), key)
  }

  ous_to_create_by_level = {
    for level in [1, 2, 3, 4, 5] : tostring(level) => {
      for key, ou in local.ous : key => ou
      if ou.level == level && !contains(keys(local.existing_ou_ids), key)
    }
  }
  accounts_to_create = {
    for key, account in local.accounts : key => account
    if !contains(keys(local.existing_account_ids), key)
  }
}

check "confirmed_architecture_contract" {
  assert {
    condition = (
      local.effective_architecture_mode != "custom" ||
      var.organization_architecture != null
    )
    error_message = "architecture_mode=custom requires a complete organization_architecture object."
  }

  assert {
    condition = (
      local.effective_architecture_mode != "default" ||
      jsonencode(local.architecture) == jsonencode(local.recommended_v1_organization_architecture)
    )
    error_message = "architecture_mode=default must use the complete recommended-v1 architecture without modifications."
  }

  assert {
    condition = (
      var.confirmed_architecture_sha256 == null ||
      (
        var.management_account_id != null &&
        var.organization_architecture != null &&
        var.architecture_mode != null &&
        var.enabled_capabilities != null
      )
    )
    error_message = "The standard confirmed-architecture path requires a verified management account, explicit architecture mode/capabilities, and a complete organization_architecture object."
  }

  assert {
    condition = (
      var.confirmed_architecture_sha256 == null ||
      length(local.accounts) > 0
    )
    error_message = "A confirmed Landing Zone architecture must contain at least one account. Emptying an applied architecture requires an explicit migration workflow."
  }
}

check "enabled_capability_contract" {
  assert {
    condition = (
      !local.effective_capabilities.finance ||
      length([for key, account in local.accounts : key if account.finance_enabled]) > 0
    )
    error_message = "The finance capability is enabled but no account has finance_enabled=true."
  }

  assert {
    condition = (
      !local.effective_capabilities.identity ||
      length([for key, account in local.accounts : key if account.identity_enabled]) > 0
    )
    error_message = "The identity capability is enabled but no account has identity_enabled=true."
  }

  assert {
    condition     = !local.effective_capabilities.log || contains(keys(local.roles), "log_archive")
    error_message = "The log capability is enabled but role_account_keys.log_archive is missing."
  }

  assert {
    condition     = !local.effective_capabilities.network || contains(keys(local.roles), "network")
    error_message = "The network capability is enabled but role_account_keys.network is missing."
  }
}

check "existing_resource_contract" {
  assert {
    condition = alltrue([
      for key in keys(local.requested_existing_ou_ids) : contains(keys(local.ous), key)
    ])
    error_message = "Every existing OU key must exist in the confirmed architecture."
  }

  assert {
    condition = alltrue([
      for key in keys(local.requested_existing_account_ids) : contains(keys(local.accounts), key)
    ])
    error_message = "Every existing account key must exist in the confirmed architecture."
  }

  assert {
    condition = alltrue([
      for key, ou in local.ous : (
        !contains(keys(local.existing_ou_ids), key) ||
        ou.level == 1 ||
        contains(keys(local.existing_ou_ids), ou.parent_key)
      )
    ])
    error_message = "A reused child OU requires its confirmed parent OU to be reused by stable key as well."
  }
}

# Existing resources are referenced by known ID and verified before reuse.
# Name-based discovery remains a read-only preflight step because the provider's
# singular data sources require IDs and its plural data sources do not expose a
# sufficiently rich parent/name catalog for unambiguous recursive matching.
data "volcenginecc_organization_unit" "existing" {
  for_each = local.existing_ou_ids

  id = each.value

  lifecycle {
    postcondition {
      condition = (
        self.name == local.ous[each.key].name &&
        self.depth == local.ous[each.key].level &&
        self.parent_id == (
          local.ous[each.key].level == 1 ?
          var.root_ou_id :
          try(local.existing_ou_ids[local.ous[each.key].parent_key], "")
        )
      )
      error_message = "Existing OU '${each.key}' does not match the requested name, level, or parent. Re-run discovery and resolve the conflict before apply."
    }
  }
}

locals {
  verified_existing_ou_ids = {
    for key, ou in data.volcenginecc_organization_unit.existing : key => ou.org_unit_id
  }
}

# Volcengine Enterprise Organization supports five OU levels. Separate resource
# blocks keep the Terraform dependency graph acyclic while still allowing a
# customer-defined parent/child topology.
resource "volcenginecc_organization_unit" "level_1" {
  for_each = local.ous_to_create_by_level["1"]

  parent_id   = var.root_ou_id
  name        = each.value.name
  description = each.value.description

  lifecycle {
    prevent_destroy = true
  }
}

locals {
  ou_ids_through_level_1 = merge(
    local.verified_existing_ou_ids,
    { for key, ou in volcenginecc_organization_unit.level_1 : key => ou.org_unit_id },
  )
  ou_paths_through_level_1 = {
    for key, ou in local.ous : key => ou.name if ou.level == 1
  }
}

resource "volcenginecc_organization_unit" "level_2" {
  for_each = local.ous_to_create_by_level["2"]

  parent_id   = local.ou_ids_through_level_1[each.value.parent_key]
  name        = each.value.name
  description = each.value.description

  lifecycle {
    prevent_destroy = true
  }
}

locals {
  ou_ids_through_level_2 = merge(
    local.ou_ids_through_level_1,
    { for key, ou in volcenginecc_organization_unit.level_2 : key => ou.org_unit_id },
  )
  ou_paths_through_level_2 = merge(
    local.ou_paths_through_level_1,
    {
      for key, ou in local.ous : key => "${local.ou_paths_through_level_1[ou.parent_key]}/${ou.name}"
      if ou.level == 2
    },
  )
}

resource "volcenginecc_organization_unit" "level_3" {
  for_each = local.ous_to_create_by_level["3"]

  parent_id   = local.ou_ids_through_level_2[each.value.parent_key]
  name        = each.value.name
  description = each.value.description

  lifecycle {
    prevent_destroy = true
  }
}

locals {
  ou_ids_through_level_3 = merge(
    local.ou_ids_through_level_2,
    { for key, ou in volcenginecc_organization_unit.level_3 : key => ou.org_unit_id },
  )
  ou_paths_through_level_3 = merge(
    local.ou_paths_through_level_2,
    {
      for key, ou in local.ous : key => "${local.ou_paths_through_level_2[ou.parent_key]}/${ou.name}"
      if ou.level == 3
    },
  )
}

resource "volcenginecc_organization_unit" "level_4" {
  for_each = local.ous_to_create_by_level["4"]

  parent_id   = local.ou_ids_through_level_3[each.value.parent_key]
  name        = each.value.name
  description = each.value.description

  lifecycle {
    prevent_destroy = true
  }
}

locals {
  ou_ids_through_level_4 = merge(
    local.ou_ids_through_level_3,
    { for key, ou in volcenginecc_organization_unit.level_4 : key => ou.org_unit_id },
  )
  ou_paths_through_level_4 = merge(
    local.ou_paths_through_level_3,
    {
      for key, ou in local.ous : key => "${local.ou_paths_through_level_3[ou.parent_key]}/${ou.name}"
      if ou.level == 4
    },
  )
}

resource "volcenginecc_organization_unit" "level_5" {
  for_each = local.ous_to_create_by_level["5"]

  parent_id   = local.ou_ids_through_level_4[each.value.parent_key]
  name        = each.value.name
  description = each.value.description

  lifecycle {
    prevent_destroy = true
  }
}

locals {
  ou_ids_by_key = merge(
    local.ou_ids_through_level_4,
    { for key, ou in volcenginecc_organization_unit.level_5 : key => ou.org_unit_id },
  )
  ou_paths_by_key = merge(
    local.ou_paths_through_level_4,
    {
      for key, ou in local.ous : key => "${local.ou_paths_through_level_4[ou.parent_key]}/${ou.name}"
      if ou.level == 5
    },
  )
}

data "volcenginecc_organization_account" "existing" {
  for_each = local.existing_account_ids

  id = each.value

  lifecycle {
    postcondition {
      condition = (
        self.account_name == local.accounts[each.key].account_name &&
        self.show_name == local.accounts[each.key].show_name &&
        (
          local.accounts[each.key].ou_key == null ?
          contains(["0", var.root_ou_id], self.org_unit_id) :
          self.org_unit_id == local.ou_ids_by_key[local.accounts[each.key].ou_key]
        )
      )
      error_message = "Existing account '${each.key}' does not match the requested name, display name, or OU. Resolve the conflict explicitly; this blueprint does not move unmanaged accounts."
    }
  }
}

resource "volcenginecc_organization_account" "account" {
  for_each = local.accounts_to_create

  account_name             = each.value.account_name
  show_name                = each.value.show_name
  org_unit_id              = each.value.ou_key == null ? "0" : local.ou_ids_by_key[each.value.ou_key]
  description              = each.value.description
  allow_console            = each.value.allow_console
  allow_exit               = each.value.allow_exit
  verification_relation_id = each.value.verification_relation_id
  tags = [
    for key, value in each.value.tags : {
      key   = key
      value = value
    }
  ]

  lifecycle {
    prevent_destroy = true
  }
}

locals {
  account_ids_by_key = merge(
    { for key, account in data.volcenginecc_organization_account.existing : key => account.account_id },
    { for key, account in volcenginecc_organization_account.account : key => account.account_id },
  )
  account_ids_by_role = {
    for role, account_key in local.roles : role => local.account_ids_by_key[account_key]
  }
  ou_catalog = {
    for key, ou in local.ous : key => {
      id          = local.ou_ids_by_key[key]
      name        = ou.name
      path        = local.ou_paths_by_key[key]
      parent_key  = ou.parent_key
      level       = ou.level
      description = ou.description
      reused      = contains(keys(local.existing_ou_ids), key)
    }
  }
  account_catalog = {
    for key, account in local.accounts : key => {
      id                      = local.account_ids_by_key[key]
      account_name            = account.account_name
      show_name               = account.show_name
      ou_key                  = account.ou_key
      ou_id                   = account.ou_key == null ? var.root_ou_id : local.ou_ids_by_key[account.ou_key]
      financial_account_alias = coalesce(account.financial_account_alias, account.account_name)
      finance_enabled         = account.finance_enabled
      identity_enabled        = account.identity_enabled
      roles                   = sort([for role, account_key in local.roles : role if account_key == key])
      reused                  = contains(keys(local.existing_account_ids), key)
    }
  }
  finance_relation_targets = {
    for key, account in local.accounts : key => {
      account_id    = local.account_ids_by_key[key]
      account_alias = coalesce(account.financial_account_alias, account.account_name)
    } if account.finance_enabled
  }
  identity_target_account_ids = distinct([
    for key in sort(keys(local.accounts)) : local.account_ids_by_key[key]
    if local.accounts[key].identity_enabled
  ])
}

# Preserve state from the original fixed default blueprint when it is upgraded
# in place. Custom architectures should retain these stable keys when they are
# modifying an already-applied default layout.
moved {
  from = volcenginecc_organization_unit.platform[0]
  to   = volcenginecc_organization_unit.level_1["platform"]
}

moved {
  from = volcenginecc_organization_unit.applications[0]
  to   = volcenginecc_organization_unit.level_1["applications"]
}

moved {
  from = volcenginecc_organization_unit.sandbox[0]
  to   = volcenginecc_organization_unit.level_1["sandbox"]
}

moved {
  from = volcenginecc_organization_unit.applications_dev[0]
  to   = volcenginecc_organization_unit.level_2["applications_dev"]
}

moved {
  from = volcenginecc_organization_unit.applications_staging[0]
  to   = volcenginecc_organization_unit.level_2["applications_staging"]
}

moved {
  from = volcenginecc_organization_unit.applications_prod[0]
  to   = volcenginecc_organization_unit.level_2["applications_prod"]
}

moved {
  from = volcenginecc_organization_account.log_archive
  to   = volcenginecc_organization_account.account["log_archive"]
}

moved {
  from = volcenginecc_organization_account.security
  to   = volcenginecc_organization_account.account["security"]
}

moved {
  from = volcenginecc_organization_account.shared_service
  to   = volcenginecc_organization_account.account["shared_service"]
}

moved {
  from = volcenginecc_organization_account.network
  to   = volcenginecc_organization_account.account["network"]
}

moved {
  from = volcenginecc_organization_account.sandbox_test
  to   = volcenginecc_organization_account.account["sandbox_test"]
}
