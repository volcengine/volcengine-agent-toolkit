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
  # financial_relation_accounts 的 key 是语义标识（如 log_archive、security、shared_service、network、sandbox_test），
  # 实际 AccountAlias = <prefix>-<key>，与 01-organization 阶段的账号命名规则保持一致，
  # 避免与其他执行或已有账号 alias 冲突。
  financial_relation_order = sort(keys(var.financial_relation_accounts))
  financial_relation_pairs = join("\n", [
    for semantic_key in local.financial_relation_order :
    "${semantic_key}\t${var.financial_relation_accounts[semantic_key]}\t${var.prefix}-${semantic_key}"
  ])
}

# ---------------------------------------------------------------
# 阶段 2：财务关系
# 火山引擎 Terraform Provider 当前不提供财务托管/财务关联资源，
# 因此本阶段使用 null_resource + local-exec 调用 ve CLI 完成。
# ---------------------------------------------------------------

resource "null_resource" "financial_relation" {
  provisioner "local-exec" {
    interpreter = ["/bin/sh", "-c"]
    command     = <<-EOT
      set -eu

      relation_name="${var.financial_relation_type}"
      case "$relation_name" in
        Financial_Hosting)
          relation_code="1"
          ;;
        Financial_Association)
          relation_code="4"
          ;;
        *)
          echo "Unsupported financial relation type: $relation_name" >&2
          exit 1
          ;;
      esac

      auth_list_str='${var.financial_relation_auth_list_str}'

      # 每行三列：语义标识 + 账号ID + 带前缀的 AccountAlias
      # AccountAlias 由 <prefix>-<semantic_key> 自动拼接，与 01-organization 阶段账号命名规则保持一致
      while IFS="$(printf '\t')" read -r semantic_key sub_account_id account_alias; do
        [ -n "$sub_account_id" ] || continue

        echo "Checking financial relation for alias=$account_alias sub_account_id=$sub_account_id relation=$relation_name($relation_code)"

        list_body=$(printf '{"AccountIDSearchList":["%s"],"Relation":["%s"]}' "$sub_account_id" "$relation_code")

        list_output=$(ve billing ListFinancialRelation --body "$list_body" 2>&1) || {
          echo "Failed to list financial relation for sub account $sub_account_id" >&2
          echo "$list_output" >&2
          exit 1
        }

        if printf '%s' "$list_output" | grep -Eq "\"SubAccountI[dD]\"[[:space:]]*:[[:space:]]*\"?$sub_account_id\"?" &&
           printf '%s' "$list_output" | grep -Eq "\"Relation\"[[:space:]]*:[[:space:]]*(\\[)?\"?$relation_code\"?(\\])?"; then
          echo "Financial relation already exists, skip: alias=$account_alias sub_account_id=$sub_account_id relation=$relation_name($relation_code)"
          continue
        fi

        if [ -n "$auth_list_str" ]; then
          create_body=$(printf '{"SubAccountID":%s,"Relation":%s,"AccountAlias":"%s","AuthListStr":"%s"}' "$sub_account_id" "$relation_code" "$account_alias" "$auth_list_str")
        else
          create_body=$(printf '{"SubAccountID":%s,"Relation":%s,"AccountAlias":"%s"}' "$sub_account_id" "$relation_code" "$account_alias")
        fi

        create_output=""
        if create_output=$(ve billing CreateFinancialRelation --body "$create_body" 2>&1); then
          :
        elif ! printf '%s' "$create_output" | grep -Eqi 'already exists|duplicate|重复|已存在|已存在其他业务关系'; then
          echo "Failed to create financial relation for sub account $sub_account_id" >&2
          echo "$create_output" >&2
          exit 1
        fi

        verify_output=$(ve billing ListFinancialRelation --body "$list_body" 2>&1) || {
          echo "Failed to verify financial relation for sub account $sub_account_id" >&2
          echo "$verify_output" >&2
          exit 1
        }

        if ! printf '%s' "$verify_output" | grep -Eq "\"SubAccountI[dD]\"[[:space:]]*:[[:space:]]*\"?$sub_account_id\"?" ||
           ! printf '%s' "$verify_output" | grep -Eq "\"Relation\"[[:space:]]*:[[:space:]]*(\\[)?\"?$relation_code\"?(\\])?"; then
          echo "Financial relation verification failed for sub account $sub_account_id" >&2
          echo "$verify_output" >&2
          exit 1
        fi

        echo "Financial relation is ready: alias=$account_alias sub_account_id=$sub_account_id relation=$relation_name($relation_code)"
        echo "$verify_output"
      done <<'EOF'
${local.financial_relation_pairs}
EOF
    EOT
  }

  triggers = {
    account_pairs = local.financial_relation_pairs
    relation_type = var.financial_relation_type
    auth_list_str = var.financial_relation_auth_list_str
  }
}
