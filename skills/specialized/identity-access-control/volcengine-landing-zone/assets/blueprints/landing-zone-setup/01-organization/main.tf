terraform {
  required_providers {
    volcenginecc = {
      source  = "volcengine/volcenginecc"
      version = ">= 0.0.41"
    }
  }
}

provider "volcenginecc" {
  region = var.region
}

locals {
  platform_ou_id             = coalesce(var.existing_platform_ou_id, try(volcenginecc_organization_unit.platform[0].org_unit_id, null))
  applications_ou_id         = coalesce(var.existing_applications_ou_id, try(volcenginecc_organization_unit.applications[0].org_unit_id, null))
  sandbox_ou_id              = coalesce(var.existing_sandbox_ou_id, try(volcenginecc_organization_unit.sandbox[0].org_unit_id, null))
  applications_dev_ou_id     = coalesce(var.existing_applications_dev_ou_id, try(volcenginecc_organization_unit.applications_dev[0].org_unit_id, null))
  applications_staging_ou_id = coalesce(var.existing_applications_staging_ou_id, try(volcenginecc_organization_unit.applications_staging[0].org_unit_id, null))
  applications_prod_ou_id    = coalesce(var.existing_applications_prod_ou_id, try(volcenginecc_organization_unit.applications_prod[0].org_unit_id, null))
}

# The Root OU ID must be resolved before apply.
# On a first-time setup, create the organization via
# `ve organization CreateOrganization --body '{}'` first, then use
# `ve organization ListOrganizationalUnits --body '{}'` to find the
# item whose Name is `Root` and Depth is `0`.
# If the organization already contains the standard OU layout,
# the caller is expected to discover those OU IDs before apply and
# pass them through the `existing_*_ou_id` inputs so Terraform reuses
# existing OUs instead of attempting to recreate them.
# --- Top-level OUs ---
resource "volcenginecc_organization_unit" "platform" {
  count = var.existing_platform_ou_id == null ? 1 : 0

  parent_id = var.root_ou_id
  name      = "Platform"
}

resource "volcenginecc_organization_unit" "applications" {
  count = var.existing_applications_ou_id == null ? 1 : 0

  parent_id  = var.root_ou_id
  name       = "Applications"
  depends_on = [volcenginecc_organization_unit.platform]
}

resource "volcenginecc_organization_unit" "sandbox" {
  count = var.existing_sandbox_ou_id == null ? 1 : 0

  parent_id  = var.root_ou_id
  name       = "SandBox"
  depends_on = [volcenginecc_organization_unit.applications]
}

resource "volcenginecc_organization_unit" "applications_dev" {
  count = var.existing_applications_dev_ou_id == null ? 1 : 0

  parent_id  = local.applications_ou_id
  name       = "Dev"
  depends_on = [volcenginecc_organization_unit.sandbox]
}

resource "volcenginecc_organization_unit" "applications_staging" {
  count = var.existing_applications_staging_ou_id == null ? 1 : 0

  parent_id  = local.applications_ou_id
  name       = "Staging"
  depends_on = [volcenginecc_organization_unit.applications_dev]
}

resource "volcenginecc_organization_unit" "applications_prod" {
  count = var.existing_applications_prod_ou_id == null ? 1 : 0

  parent_id  = local.applications_ou_id
  name       = "Prod"
  depends_on = [volcenginecc_organization_unit.applications_staging]
}

# --- Core Accounts (account_name max 20 chars) ---
resource "volcenginecc_organization_account" "log_archive" {
  account_name = "${var.prefix}-Log"
  show_name    = "${var.prefix}-LogArchiveAccount"
  org_unit_id  = local.platform_ou_id

  depends_on = [volcenginecc_organization_unit.applications_prod]
}

resource "volcenginecc_organization_account" "security" {
  account_name = "${var.prefix}-Sec"
  show_name    = "${var.prefix}-SecurityAccount"
  org_unit_id  = local.platform_ou_id

  depends_on = [volcenginecc_organization_account.log_archive]
}

resource "volcenginecc_organization_account" "shared_service" {
  account_name = "${var.prefix}-Shared"
  show_name    = "${var.prefix}-SharedServiceAccount"
  org_unit_id  = local.platform_ou_id

  depends_on = [volcenginecc_organization_account.security]
}

resource "volcenginecc_organization_account" "network" {
  account_name = "${var.prefix}-Net"
  show_name    = "${var.prefix}-NetworkAccount"
  org_unit_id  = local.platform_ou_id

  depends_on = [volcenginecc_organization_account.shared_service]
}

resource "volcenginecc_organization_account" "sandbox_test" {
  account_name = "${var.prefix}-SandBox"
  show_name    = "${var.prefix}-SandBoxTestAccount"
  org_unit_id  = local.sandbox_ou_id

  depends_on = [volcenginecc_organization_account.network]
}
