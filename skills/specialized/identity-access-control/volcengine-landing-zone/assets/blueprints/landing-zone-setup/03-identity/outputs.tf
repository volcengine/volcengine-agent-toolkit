output "permission_set_admin_id" {
  description = "Administrator 权限集 ID"
  value       = volcenginecc_cloudidentity_permission_set.admin.permission_set_id
}

output "permission_set_readonly_id" {
  description = "ReadOnly 权限集 ID"
  value       = volcenginecc_cloudidentity_permission_set.readonly.permission_set_id
}

output "permission_set_ops_admin_id" {
  description = "OpsAdministrator 权限集 ID"
  value       = volcenginecc_cloudidentity_permission_set.ops_admin.permission_set_id
}

output "permission_set_financial_admin_id" {
  description = "FinancialAdministrator 权限集 ID"
  value       = volcenginecc_cloudidentity_permission_set.financial_admin.permission_set_id
}

output "permission_set_iam_admin_id" {
  description = "IAMAdministrator 权限集 ID"
  value       = volcenginecc_cloudidentity_permission_set.iam_admin.permission_set_id
}

output "admin_user_id" {
  description = "管理员用户 ID"
  value       = volcenginecc_cloudidentity_user.admin.user_id
}

output "admin_password_reset_status" {
  description = "管理员初始密码重置状态"
  value       = "completed"
}

output "admin_password_reset_result_path" {
  description = "管理员初始密码重置结果文件路径"
  value       = local.admin_password_result_path
}

output "permission_set_catalog" {
  description = "面向用户展示的权限集说明与适用场景"
  value = [
    {
      name        = "AdministratorAccess"
      description = "管理员权限，适合平台初始化、资源治理和全局配置维护。"
      typical_scenarios = [
        "首次搭建 Landing Zone",
        "处理组织、网络、日志等基础设施变更",
        "排查需要全局权限的问题",
      ]
      assignment_status = "已自动分配到当前管理员用户，并已下发到管理账号和目标账号列表"
    },
    {
      name        = "ReadOnlyAccess"
      description = "只读权限，适合审计、查看配置和日常巡检。"
      typical_scenarios = [
        "查看资源与配置状态",
        "审计和合规检查",
        "排障前的信息确认",
      ]
      assignment_status = "当前仅创建，未自动分配"
    },
    {
      name        = "OpsAdministrator"
      description = "运维管理权限（除账号信息、企业组织、云身份中心、访问控制和费用中心外的其他全部权限），适合日常运维、监控和故障处理。"
      typical_scenarios = [
        "处理告警和运维变更",
        "执行日常运维操作",
        "定位和修复运行故障",
      ]
      assignment_status = "当前仅创建，未自动分配"
    },
    {
      name        = "FinancialAdministrator"
      description = "财务管理权限，适合账单、费用和财务关系管理。"
      typical_scenarios = [
        "查看账单与费用分析",
        "管理财务托管或财务关联",
        "核对成本分摊与预算",
      ]
      assignment_status = "当前仅创建，未自动分配"
    },
    {
      name        = "IAMAdministrator"
      description = "身份与访问管理权限，适合用户、权限和访问控制治理。"
      typical_scenarios = [
        "管理用户与权限边界",
        "调整访问授权策略",
        "治理身份与访问控制配置",
      ]
      assignment_status = "当前仅创建，未自动分配"
    },
  ]
}

output "admin_assignment_target_ids" {
  description = "已自动分配 AdministratorAccess 的账号 ID 列表（包含管理账号和目标账号列表）"
  value       = sort(tolist(local.target_account_ids))
}

output "cloud_identity_portal_url" {
  description = "Cloud Identity 用户门户域名（不含路径），来自实例实际配置"
  value       = data.external.portal_login.result.portal_url
}

output "cloud_identity_subdomain" {
  description = "Cloud Identity 实例子域名 / 实例标识"
  value       = data.external.portal_login.result.subdomain
}

output "recommended_login_url" {
  description = "建议提供给用户的登录入口 URL（Cloud Identity 用户门户）"
  value       = data.external.portal_login.result.login_url
}
