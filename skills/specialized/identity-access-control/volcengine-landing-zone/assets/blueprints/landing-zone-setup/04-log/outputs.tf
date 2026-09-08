output "audit_log_bucket_name" {
  description = "审计日志 TOS Bucket 名称"
  value       = "${var.prefix}-organization-audit-logs"
}

output "trail_name" {
  description = "组织级操作审计跟踪名称"
  value       = "${var.prefix}-org-trail"
}
