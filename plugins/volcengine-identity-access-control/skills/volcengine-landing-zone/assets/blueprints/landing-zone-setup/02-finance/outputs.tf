output "financial_relations" {
  description = "已建立财务关系的账号列表；key 为稳定账号标识，alias 来自 01 架构或旧输入兼容逻辑"
  value = {
    for key, target in local.financial_relation_targets : key => {
      account_id    = target.account_id
      account_alias = target.account_alias
      relation_type = var.financial_relation_type
    }
  }
}
