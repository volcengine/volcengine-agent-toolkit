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
  # 标签键值通过 base64(JSON) 传给 Python helper，由 helper 以参数数组方式拼装并执行
  # `ve organization TagResources`，避免在 shell 中直接插值带来词法拆分/命令注入风险。
  account_tags_json_b64           = base64encode(jsonencode(var.account_tags))
  account_tag_validation_json_b64 = local.account_tags_json_b64
}

resource "volcenginecc_organization_account" "account" {
  account_name = var.account_name
  show_name    = var.show_name
  org_unit_id  = var.target_ou_id
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

      list_body=$(printf '{"AccountIDSearchList":["%s"],"Relation":["%s"]}' "$sub_account_id" "$relation_code")
      list_output=$(ve billing ListFinancialRelation --body "$list_body" 2>&1) || {
        echo "Failed to list financial relation for account $sub_account_id" >&2
        echo "$list_output" >&2
        exit 1
      }

      if printf '%s' "$list_output" | grep -Eq "\"SubAccountI[dD]\"[[:space:]]*:[[:space:]]*\"?$sub_account_id\"?" &&
         printf '%s' "$list_output" | grep -Eq "\"Relation\"[[:space:]]*:[[:space:]]*(\\[)?\"?$relation_code\"?(\\])?"; then
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

      if ! printf '%s' "$verify_output" | grep -Eq "\"SubAccountI[dD]\"[[:space:]]*:[[:space:]]*\"?$sub_account_id\"?" ||
         ! printf '%s' "$verify_output" | grep -Eq "\"Relation\"[[:space:]]*:[[:space:]]*(\\[)?\"?$relation_code\"?(\\])?"; then
        echo "Financial relation verification failed for account $sub_account_id" >&2
        echo "$verify_output" >&2
        exit 1
      fi

      echo "$create_output"
    EOT
  }

  depends_on = [volcenginecc_organization_account.account]
}

resource "null_resource" "account_tags" {
  count = length(var.account_tags) > 0 ? 1 : 0

  triggers = {
    account_id   = volcenginecc_organization_account.account.account_id
    account_tags = jsonencode(var.account_tags)
  }

  provisioner "local-exec" {
    interpreter = ["/bin/sh", "-c"]
    command     = <<-EOT
      set -eu

      account_id="${volcenginecc_organization_account.account.account_id}"

      # 通过 Python helper 以参数数组方式调用 `ve organization TagResources`，
      # 标签键值不进入 shell 词法解析，规避空格/特殊字符导致的拆分与命令注入。
      tag_output="$(ACCOUNT_ID="$account_id" TAGS_JSON_B64='${local.account_tags_json_b64}' python3 - <<'PY'
import base64
import json
import os
import subprocess
import sys

account_id = os.environ["ACCOUNT_ID"]
tags = json.loads(base64.b64decode(os.environ["TAGS_JSON_B64"]).decode("utf-8"))

cmd = [
    "ve",
    "organization",
    "TagResources",
    "--ResourceIds.1",
    account_id,
    "--ResourceType",
    "account",
]
for idx, tag in enumerate(tags, start=1):
    cmd.extend([f"--Tags.{idx}.Key", str(tag["key"])])
    cmd.extend([f"--Tags.{idx}.Value", str(tag["value"])])

completed = subprocess.run(cmd, text=True, capture_output=True)
sys.stdout.write(completed.stdout)
sys.stderr.write(completed.stderr)
raise SystemExit(completed.returncode)
PY
      )" || {
        echo "Failed to tag account $account_id" >&2
        echo "$tag_output" >&2
        exit 1
      }

      verify_output=$(ve organization ListTagResources \
        --ResourceIds.1 "$account_id" \
        --ResourceType "account" 2>&1) || {
        echo "Failed to verify account tags for $account_id" >&2
        echo "$verify_output" >&2
        exit 1
      }

      tag_validation_output="$(EXPECTED_TAGS_JSON_B64='${local.account_tag_validation_json_b64}' LIST_TAG_RESOURCES_OUTPUT="$verify_output" python3 - <<'PY'
import base64
import json
import os
import sys

expected_tags = json.loads(
    base64.b64decode(os.environ["EXPECTED_TAGS_JSON_B64"]).decode("utf-8")
)
payload = json.loads(os.environ["LIST_TAG_RESOURCES_OUTPUT"])
actual_pairs = set()


def walk(node):
    if isinstance(node, dict):
        key = node.get("TagKey", node.get("Key"))
        if key is not None:
            if "TagValue" in node:
                actual_pairs.add((str(key), str(node["TagValue"])))
            elif "Value" in node:
                actual_pairs.add((str(key), str(node["Value"])))
        for value in node.values():
            walk(value)
    elif isinstance(node, list):
        for item in node:
            walk(item)


walk(payload)
missing_pairs = [
    f'{tag["key"]}={tag["value"]}'
    for tag in expected_tags
    if (str(tag["key"]), str(tag["value"])) not in actual_pairs
]

if missing_pairs:
    print(
        "missing expected tag pairs: " + ", ".join(missing_pairs),
        file=sys.stderr,
    )
    raise SystemExit(1)

print("Account tag verification passed")
PY
      )" || {
        echo "Account tag verification failed for $account_id" >&2
        echo "$tag_validation_output" >&2
        echo "$verify_output" >&2
        exit 1
      }

      echo "$tag_output"
    EOT
  }

  depends_on = [volcenginecc_organization_account.account]
}
