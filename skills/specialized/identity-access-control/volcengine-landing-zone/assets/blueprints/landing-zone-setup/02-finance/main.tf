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

locals {
  landing_zone_context = var.landing_zone_context_path == null ? null : try(
    jsondecode(file(var.landing_zone_context_path)),
    null,
  )
  context_financial_relation_targets = {
    for key, target in try(local.landing_zone_context.phase_inputs.finance.targets, {}) : key => {
      account_id    = tostring(target.account_id)
      account_alias = tostring(target.account_alias)
    }
  }
  legacy_financial_relation_targets = var.financial_relation_targets != null ? var.financial_relation_targets : {
    for key, account_id in var.financial_relation_accounts : key => {
      account_id    = account_id
      account_alias = "${var.prefix}-${key}"
    }
  }
  # The filtered Phase 01 context is authoritative when provided. Legacy
  # variables remain available for existing standalone workspaces only.
  financial_relation_targets = var.landing_zone_context_path != null ? local.context_financial_relation_targets : local.legacy_financial_relation_targets
  financial_relation_order   = sort(keys(local.financial_relation_targets))
  financial_relation_pairs = join("\n", [
    for account_key in local.financial_relation_order :
    "${account_key}\t${local.financial_relation_targets[account_key].account_id}\t${local.financial_relation_targets[account_key].account_alias}"
  ])
  confirmed_architecture_path = var.landing_zone_context_path == null ? null : "${dirname(var.landing_zone_context_path)}/confirmed-architecture.json"
  architecture_hash_matches = var.landing_zone_context_path == null ? true : try(
    filesha256(local.confirmed_architecture_path) == local.landing_zone_context.configuration.architecture_sha256,
    false,
  )
}

check "landing_zone_context_contract" {
  assert {
    condition     = var.landing_zone_context_path == null ? true : local.landing_zone_context != null
    error_message = "landing_zone_context_path must reference readable, valid JSON."
  }

  assert {
    condition = var.landing_zone_context_path == null ? true : (
      try(local.landing_zone_context.contract_version, null) == 1 &&
      try(local.landing_zone_context.configuration.schema_version, null) == 1
    )
    error_message = "The Landing Zone context contract/schema version is unsupported."
  }

  assert {
    condition = var.landing_zone_context_path == null ? true : (
      try(local.landing_zone_context.configuration.prefix, null) == var.prefix &&
      try(local.landing_zone_context.configuration.region, null) == var.region
    )
    error_message = "The finance phase prefix/region must match the confirmed Landing Zone context."
  }

  assert {
    condition     = local.architecture_hash_matches
    error_message = "confirmed-architecture.json does not match the architecture digest recorded in landing-zone-context.json."
  }

  assert {
    condition     = var.landing_zone_context_path == null ? true : try(local.landing_zone_context.phase_inputs.finance.enabled, false)
    error_message = "The finance capability is disabled in the confirmed Landing Zone design; skip Phase 02."
  }
}

check "legacy_finance_input_compatibility" {
  assert {
    condition = (
      var.landing_zone_context_path == null ||
      var.financial_relation_targets == null ||
      var.financial_relation_targets == local.context_financial_relation_targets
    )
    error_message = "financial_relation_targets conflicts with the authoritative Landing Zone context."
  }

  assert {
    condition = (
      var.landing_zone_context_path == null ||
      length(var.financial_relation_accounts) == 0 ||
      var.financial_relation_accounts == {
        for key, target in local.context_financial_relation_targets : key => target.account_id
      }
    )
    error_message = "financial_relation_accounts conflicts with the authoritative Landing Zone context."
  }
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

      # 用结构化 JSON 解析判断“该子账号 + 关系是否已存在”。
      # 旧实现用两条独立 grep 分别匹配 SubAccountId 和 Relation，会跨记录误命中
      # （字段 A 命中记录①、字段 B 命中记录②）从而把未建的关系误判为已存在。
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

      # 每行三列：稳定账号 key + 账号 ID + 经 01 架构确认的 AccountAlias
      while IFS="$(printf '\t')" read -r account_key sub_account_id account_alias; do
        [ -n "$sub_account_id" ] || continue

        echo "Checking financial relation for alias=$account_alias sub_account_id=$sub_account_id relation=$relation_name($relation_code)"

        list_body=$(printf '{"AccountIDSearchList":["%s"],"Relation":["%s"]}' "$sub_account_id" "$relation_code")

        list_output=$(ve billing ListFinancialRelation --body "$list_body" 2>&1) || {
          echo "Failed to list financial relation for sub account $sub_account_id" >&2
          echo "$list_output" >&2
          exit 1
        }

        if relation_exists "$list_output" "$sub_account_id" "$relation_code"; then
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

        if ! relation_exists "$verify_output" "$sub_account_id" "$relation_code"; then
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
