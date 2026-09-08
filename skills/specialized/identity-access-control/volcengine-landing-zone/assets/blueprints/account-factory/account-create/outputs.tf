output "account_id" {
  description = "新创建账号的账号 ID"
  value       = volcenginecc_organization_account.account.account_id
}

output "account_name" {
  description = "新创建账号的账号名"
  value       = volcenginecc_organization_account.account.account_name
}

output "show_name" {
  description = "新创建账号的展示名称"
  value       = volcenginecc_organization_account.account.show_name
}

output "target_ou_id" {
  description = "账号放置的目标 OU ID"
  value       = var.target_ou_id
}
