output "financial_relations" {
  description = "已建立财务关系的账号列表；key 为语义标识，AccountAlias = <prefix>-<key>"
  value = {
    for k, v in var.financial_relation_accounts : k => {
      account_id    = v
      account_alias = "${var.prefix}-${k}"
      relation_type = var.financial_relation_type
    }
  }
}
