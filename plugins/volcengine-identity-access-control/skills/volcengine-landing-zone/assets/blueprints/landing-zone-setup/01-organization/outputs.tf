output "architecture_mode" {
  description = "Selected architecture branch: default or custom"
  value       = local.effective_architecture_mode
}

output "ou_ids_by_key" {
  description = "All requested OU IDs indexed by stable logical key"
  value       = local.ou_ids_by_key
}

output "ou_catalog" {
  description = "Resolved OU catalog for later account placement and reporting"
  value       = local.ou_catalog
}

output "account_ids_by_key" {
  description = "All requested organization account IDs indexed by stable logical key"
  value       = local.account_ids_by_key
}

output "account_ids_by_role" {
  description = "Organization account IDs indexed by Landing Zone semantic role"
  value       = local.account_ids_by_role
}

output "account_catalog" {
  description = "Resolved account catalog for downstream finance, identity, logging, networking, and reporting phases"
  value       = local.account_catalog
}

output "finance_relation_targets" {
  description = "Default Phase 02 targets selected by the account architecture"
  value       = local.finance_relation_targets
}

output "identity_target_account_ids" {
  description = "De-duplicated Phase 03 target account IDs selected by the account architecture"
  value       = local.identity_target_account_ids
}

output "landing_zone_context_payload" {
  description = "Filtered, non-sensitive Phase 01 hand-off payload. The Agent adds Terraform state lineage and serial before writing landing-zone-context.json."
  value = {
    contract_version = 1
    configuration = {
      schema_version       = var.configuration_schema_version
      architecture_profile = var.architecture_profile
      architecture_mode    = local.effective_architecture_mode
      architecture_sha256  = local.effective_architecture_sha256
      prefix               = var.prefix
      region               = var.region
      capabilities         = local.effective_capabilities
    }
    execution_scope = {
      management_account_id = var.management_account_id
      organization_id       = var.organization_id
      root_ou_id            = var.root_ou_id
    }
    organization = {
      ou_catalog          = local.ou_catalog
      account_catalog     = local.account_catalog
      account_ids_by_key  = local.account_ids_by_key
      account_ids_by_role = local.account_ids_by_role
    }
    phase_inputs = {
      finance = {
        enabled = local.effective_capabilities.finance
        targets = local.effective_capabilities.finance ? local.finance_relation_targets : {}
      }
      identity = {
        enabled            = local.effective_capabilities.identity
        target_account_ids = local.effective_capabilities.identity ? local.identity_target_account_ids : []
      }
      log = {
        enabled    = local.effective_capabilities.log
        account_id = local.effective_capabilities.log ? try(local.account_ids_by_role["log_archive"], null) : null
      }
      network = {
        enabled    = local.effective_capabilities.network
        account_id = local.effective_capabilities.network ? try(local.account_ids_by_role["network"], null) : null
      }
    }
  }
}

# Compatibility outputs for the original default blueprint and downstream
# consumers. Custom architectures may omit these OU keys or semantic roles, in
# which case the corresponding compatibility output is null.
output "ou_platform_id" {
  description = "Platform OU ID when the stable key exists"
  value       = try(local.ou_ids_by_key["platform"], null)
}

output "ou_applications_id" {
  description = "Applications OU ID when the stable key exists"
  value       = try(local.ou_ids_by_key["applications"], null)
}

output "ou_applications_dev_id" {
  description = "Applications Dev OU ID when the stable key exists"
  value       = try(local.ou_ids_by_key["applications_dev"], null)
}

output "ou_applications_staging_id" {
  description = "Applications Staging OU ID when the stable key exists"
  value       = try(local.ou_ids_by_key["applications_staging"], null)
}

output "ou_applications_prod_id" {
  description = "Applications Prod OU ID when the stable key exists"
  value       = try(local.ou_ids_by_key["applications_prod"], null)
}

output "ou_sandbox_id" {
  description = "SandBox OU ID when the stable key exists"
  value       = try(local.ou_ids_by_key["sandbox"], null)
}

output "account_id_log_archive" {
  description = "Account ID bound to the log_archive role"
  value       = try(local.account_ids_by_role["log_archive"], null)
}

output "account_id_security" {
  description = "Account ID bound to the security role"
  value       = try(local.account_ids_by_role["security"], null)
}

output "account_id_shared_service" {
  description = "Account ID bound to the shared_service role"
  value       = try(local.account_ids_by_role["shared_service"], null)
}

output "account_id_network" {
  description = "Account ID bound to the network role"
  value       = try(local.account_ids_by_role["network"], null)
}

output "account_id_sandbox_test" {
  description = "Account ID bound to the sandbox_test role"
  value       = try(local.account_ids_by_role["sandbox_test"], null)
}
