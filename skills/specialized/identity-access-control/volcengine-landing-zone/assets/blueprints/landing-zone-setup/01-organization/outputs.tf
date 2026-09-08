output "ou_platform_id" {
  description = "Platform OU ID"
  value       = local.platform_ou_id
}

output "ou_applications_id" {
  description = "Applications OU ID"
  value       = local.applications_ou_id
}

output "ou_applications_dev_id" {
  description = "Applications Dev OU ID"
  value       = local.applications_dev_ou_id
}

output "ou_applications_staging_id" {
  description = "Applications Staging OU ID"
  value       = local.applications_staging_ou_id
}

output "ou_applications_prod_id" {
  description = "Applications Prod OU ID"
  value       = local.applications_prod_ou_id
}

output "ou_sandbox_id" {
  description = "SandBox OU ID"
  value       = local.sandbox_ou_id
}

output "account_id_log_archive" {
  description = "LogArchive 账号 ID"
  value       = volcenginecc_organization_account.log_archive.account_id
}

output "account_id_security" {
  description = "Security 账号 ID"
  value       = volcenginecc_organization_account.security.account_id
}

output "account_id_shared_service" {
  description = "SharedService 账号 ID"
  value       = volcenginecc_organization_account.shared_service.account_id
}

output "account_id_network" {
  description = "Network 账号 ID"
  value       = volcenginecc_organization_account.network.account_id
}

output "account_id_sandbox_test" {
  description = "SandBoxTest 账号 ID"
  value       = volcenginecc_organization_account.sandbox_test.account_id
}
