terraform {
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

resource "volcenginecc_organization_account" "account" {
  account_name = var.account_name
  show_name    = var.show_name
  org_unit_id  = var.target_ou_id
  tags         = var.account_tags
}

resource "null_resource" "financial_relation" {
  triggers = {
    account_id                       = volcenginecc_organization_account.account.account_id
    financial_relation_type          = var.financial_relation_type
    financial_relation_auth_list_str = var.financial_relation_auth_list_str
    financial_relation_account_alias = var.financial_relation_account_alias
  }

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

      sub_account_id="${volcenginecc_organization_account.account.account_id}"
      auth_list_str="${var.financial_relation_auth_list_str}"
      requested_account_alias="${var.financial_relation_account_alias}"
      account_alias="$requested_account_alias"
      account_alias_source="user"
      if [ -z "$account_alias" ]; then
        account_alias="${var.account_name}"
        account_alias_source="auto"
      fi
      fallback_account_alias="${var.account_name}-$sub_account_id"

      # 用结构化 JSON 解析判断“该子账号 + 关系是否已存在”，避免两条独立 grep
      # 跨记录误命中（字段 A 命中记录①、字段 B 命中记录②）把未建关系误判为已存在。
      relation_exists() {
        RELATION_OUTPUT="$1" python3 - "$2" "$3" <<'PY'
import json
import os
import sys

sub_account_id = sys.argv[1]
relation_code = sys.argv[2]
raw = os.environ.get("RELATION_OUTPUT", "")
start = raw.find("{")
if start == -1:
    raise SystemExit(1)
try:
    payload = json.loads(raw[start:])
except json.JSONDecodeError:
    raise SystemExit(1)
result = payload.get("Result", {}) or {}
# ListFinancialRelation (billing 2022-01-01) 实际返回 Result.List；旧字段名 FinancialRelations 仅作兼容兜底
relations = result.get("List", result.get("FinancialRelations", [])) or []
for relation in relations:
    rid = str(relation.get("SubAccountId", relation.get("SubAccountID", "")))
    value = relation.get("Relation", "")
    codes = [str(item) for item in value] if isinstance(value, list) else [str(value)]
    if rid == sub_account_id and relation_code in codes:
        raise SystemExit(0)
raise SystemExit(1)
PY
      }

      list_body=$(printf '{"AccountIDSearchList":["%s"],"Relation":["%s"]}' "$sub_account_id" "$relation_code")
      list_output=$(ve billing ListFinancialRelation --body "$list_body" 2>&1) || {
        echo "Failed to list financial relation for account $sub_account_id" >&2
        echo "$list_output" >&2
        exit 1
      }

      if relation_exists "$list_output" "$sub_account_id" "$relation_code"; then
        echo "Financial relation already exists for account $sub_account_id, skip"
        exit 0
      fi

      # CreateFinancialRelation binds the master account from the current caller context.
      build_create_body() {
        create_account_alias="$1"
        if [ -n "$auth_list_str" ] && [ -n "$create_account_alias" ]; then
          printf '{"SubAccountID":%s,"Relation":%s,"AuthListStr":"%s","AccountAlias":"%s"}' "$sub_account_id" "$relation_code" "$auth_list_str" "$create_account_alias"
        elif [ -n "$auth_list_str" ]; then
          printf '{"SubAccountID":%s,"Relation":%s,"AuthListStr":"%s"}' "$sub_account_id" "$relation_code" "$auth_list_str"
        elif [ -n "$create_account_alias" ]; then
          printf '{"SubAccountID":%s,"Relation":%s,"AccountAlias":"%s"}' "$sub_account_id" "$relation_code" "$create_account_alias"
        else
          printf '{"SubAccountID":%s,"Relation":%s}' "$sub_account_id" "$relation_code"
        fi
      }

      create_output=""
      create_body="$(build_create_body "$account_alias")"
      if create_output=$(ve billing CreateFinancialRelation --body "$create_body" 2>&1); then
        :
      elif printf '%s' "$create_output" | grep -Eqi 'OperationDenied\.AccountAliasExist|AccountAliasExist'; then
        if [ "$account_alias_source" = "user" ]; then
          echo "Financial relation alias conflict for account $sub_account_id: explicit AccountAlias '$account_alias' already exists" >&2
          echo "$create_output" >&2
          exit 1
        fi

        if [ "$fallback_account_alias" = "$account_alias" ]; then
          echo "Financial relation alias conflict for account $sub_account_id and no alternate alias is available" >&2
          echo "$create_output" >&2
          exit 1
        fi

        account_alias="$fallback_account_alias"
        create_body="$(build_create_body "$account_alias")"
        if create_output=$(ve billing CreateFinancialRelation --body "$create_body" 2>&1); then
          :
        elif ! printf '%s' "$create_output" | grep -Eqi 'already exists|duplicate|重复|已存在'; then
          echo "Failed to create financial relation for account $sub_account_id" >&2
          echo "$create_output" >&2
          exit 1
        fi
      elif ! printf '%s' "$create_output" | grep -Eqi 'already exists|duplicate|重复|已存在'; then
        echo "Failed to create financial relation for account $sub_account_id" >&2
        echo "$create_output" >&2
        exit 1
      fi

      verify_output=$(ve billing ListFinancialRelation --body "$list_body" 2>&1) || {
        echo "Failed to verify financial relation for account $sub_account_id" >&2
        echo "$verify_output" >&2
        exit 1
      }

      if ! relation_exists "$verify_output" "$sub_account_id" "$relation_code"; then
        echo "Financial relation verification failed for account $sub_account_id" >&2
        echo "$verify_output" >&2
        exit 1
      fi

      echo "$create_output"
    EOT
  }

  depends_on = [volcenginecc_organization_account.account]
}
