terraform {
  required_providers {
    null = {
      source  = "hashicorp/null"
      version = ">= 3.2.1"
    }
    external = {
      source  = "hashicorp/external"
      version = ">= 2.3.1"
    }
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
  context_core_account_ids = [
    for account_id in try(local.landing_zone_context.phase_inputs.identity.target_account_ids, []) :
    tostring(account_id)
  ]
  effective_core_account_ids = var.landing_zone_context_path != null ? local.context_core_account_ids : (
    var.core_account_ids == null ? [] : var.core_account_ids
  )
  effective_management_account_id = var.landing_zone_context_path != null ? try(
    local.landing_zone_context.execution_scope.management_account_id == null ? "" : trimspace(tostring(local.landing_zone_context.execution_scope.management_account_id)),
    "",
  ) : (var.management_account_id == null ? "" : trimspace(var.management_account_id))
  confirmed_architecture_path = var.landing_zone_context_path == null ? null : "${dirname(var.landing_zone_context_path)}/confirmed-architecture.json"
  architecture_hash_matches = var.landing_zone_context_path == null ? true : try(
    filesha256(local.confirmed_architecture_path) == local.landing_zone_context.configuration.architecture_sha256,
    false,
  )
  workspace_root             = abspath("${path.module}/../../..")
  identity_runtime_dir       = "${local.workspace_root}/landing-zone-setup/identity/${var.admin_username}"
  admin_password_result_path = "${local.identity_runtime_dir}/admin-password-reset.json"
  normalized_admin_email     = var.admin_email != null && trimspace(var.admin_email) != "" ? trimspace(var.admin_email) : null
  target_account_ids = toset(distinct(concat(
    [local.effective_management_account_id],
    [for account_id in local.effective_core_account_ids : trimspace(account_id) if trimspace(account_id) != ""]
  )))
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
    error_message = "The identity phase prefix/region must match the confirmed Landing Zone context."
  }

  assert {
    condition     = local.architecture_hash_matches
    error_message = "confirmed-architecture.json does not match the architecture digest recorded in landing-zone-context.json."
  }

  assert {
    condition     = var.landing_zone_context_path == null ? true : try(local.landing_zone_context.phase_inputs.identity.enabled, false)
    error_message = "The identity capability is disabled in the confirmed Landing Zone design; skip Phase 03."
  }

  assert {
    condition     = local.effective_management_account_id != ""
    error_message = "A verified management account ID is required."
  }
}

check "legacy_identity_input_compatibility" {
  assert {
    condition = (
      var.landing_zone_context_path == null ||
      var.core_account_ids == null ||
      sort(distinct(var.core_account_ids)) == sort(distinct(local.context_core_account_ids))
    )
    error_message = "core_account_ids conflicts with the authoritative Landing Zone context."
  }

  assert {
    condition = (
      var.landing_zone_context_path == null ||
      var.management_account_id == null ||
      trimspace(var.management_account_id) == local.effective_management_account_id
    )
    error_message = "management_account_id conflicts with the authoritative Landing Zone context."
  }
}

# Cloud Identity writes in this stage are sensitive to control-plane task
# concurrency. Callers must run this module with `terraform plan/apply
# -parallelism=1`; otherwise assignment/provisioning may return
# `ConcurrentException` during apply.

# --- Permission Set: Administrator ---
resource "volcenginecc_cloudidentity_permission_set" "admin" {
  name             = "AdministratorAccess"
  description      = "Full administrator access for Landing Zone core accounts"
  session_duration = var.session_duration
  permission_policies = [
    {
      permission_policy_name     = "AdministratorAccess"
      permission_policy_type     = "System"
      permission_policy_document = ""
    }
  ]
}

# --- Permission Set: ReadOnly ---
resource "volcenginecc_cloudidentity_permission_set" "readonly" {
  name             = "ReadOnlyAccess"
  description      = "Read-only access for auditing and review"
  session_duration = var.session_duration
  permission_policies = [
    {
      permission_policy_name     = "ReadOnlyAccess"
      permission_policy_type     = "System"
      permission_policy_document = ""
    }
  ]

  depends_on = [volcenginecc_cloudidentity_permission_set.admin]
}

resource "volcenginecc_cloudidentity_permission_set" "ops_admin" {
  name             = "OpsAdministrator"
  description      = "Operations administrator access for Landing Zone"
  session_duration = var.session_duration
  permission_policies = [
    {
      permission_policy_name     = "OpsAdministrator"
      permission_policy_type     = "System"
      permission_policy_document = ""
    }
  ]

  depends_on = [volcenginecc_cloudidentity_permission_set.readonly]
}

resource "volcenginecc_cloudidentity_permission_set" "financial_admin" {
  name             = "FinancialAdministrator"
  description      = "Financial administrator access for Landing Zone"
  session_duration = var.session_duration
  permission_policies = [
    {
      permission_policy_name     = "FinancialAdministrator"
      permission_policy_type     = "System"
      permission_policy_document = ""
    }
  ]

  depends_on = [volcenginecc_cloudidentity_permission_set.ops_admin]
}

resource "volcenginecc_cloudidentity_permission_set" "iam_admin" {
  name             = "IAMAdministrator"
  description      = "IAM administrator access for Landing Zone"
  session_duration = var.session_duration
  permission_policies = [
    {
      permission_policy_name     = "IAMAdministrator"
      permission_policy_type     = "System"
      permission_policy_document = ""
    }
  ]

  depends_on = [volcenginecc_cloudidentity_permission_set.financial_admin]
}

# --- Admin User ---
resource "volcenginecc_cloudidentity_user" "admin" {
  user_name    = var.admin_username
  display_name = var.admin_display_name
  email        = local.normalized_admin_email

  depends_on = [volcenginecc_cloudidentity_permission_set.iam_admin]
}

# --- Admin Permission Set Assignment (management + target accounts) ---
resource "volcenginecc_cloudidentity_permission_set_assignment" "admin_assign" {
  for_each = local.target_account_ids

  permission_set_id = volcenginecc_cloudidentity_permission_set.admin.permission_set_id
  principal_type    = "User"
  principal_id      = volcenginecc_cloudidentity_user.admin.user_id
  target_id         = each.value
}

# --- Provision the permission set to management + target accounts ---
resource "volcenginecc_cloudidentity_permission_set_provisioning" "admin_provision" {
  for_each = local.target_account_ids

  permission_set_id = volcenginecc_cloudidentity_permission_set.admin.permission_set_id
  target_id         = each.value

  depends_on = [volcenginecc_cloudidentity_permission_set_assignment.admin_assign]
}

resource "null_resource" "admin_password_reset" {
  triggers = {
    target_account_ids = join(",", sort(tolist(local.target_account_ids)))
    admin_user_id      = volcenginecc_cloudidentity_user.admin.user_id
    admin_username     = var.admin_username
  }

  provisioner "local-exec" {
    interpreter = ["/bin/sh", "-c"]
    command     = <<-EOT
      set -eu
      umask 077

      runtime_dir="${local.identity_runtime_dir}"
      result_file="${local.admin_password_result_path}"
      temp_result_file="$${result_file}.tmp.$$"

      mkdir -p "$runtime_dir"
      chmod 700 "$runtime_dir"

      cleanup() {
        cleanup_status=$?
        rm -f "$temp_result_file"
        exit "$cleanup_status"
      }
      trap cleanup EXIT INT TERM

      ve cloudidentity ResetPassword --body '{
        "GenerateRandomPassword": true,
        "PasswordResetRequired": true,
        "UserId": "${volcenginecc_cloudidentity_user.admin.user_id}"
      }' > "$temp_result_file"

      chmod 600 "$temp_result_file"
      mv "$temp_result_file" "$result_file"
      chmod 600 "$result_file"
      trap - EXIT INT TERM

      echo "Admin password reset result written to $result_file"
      EOT
  }

  depends_on = [volcenginecc_cloudidentity_permission_set_provisioning.admin_provision]
}

# --- Resolve the Cloud Identity user-portal login entry (dynamic, not hard-coded) ---
# Queries the live Cloud Identity instance so the login URL we hand to the user is
# the real user portal (https://<subdomain>.volccloudidentity.com/userportal),
# instead of the generic console login page.
data "external" "portal_login" {
  program = ["/bin/sh", "-c", <<-EOT
    set -eu

    # 用结构化 JSON 解析门户配置，避免 sed 抠字段对响应格式的脆弱假设。
    # 优先 GetPortalLoginConfig.PortalURL（权威完整域名），否则回退到
    # GetServiceStatus 的实例字段拼装 user portal 入口。
    config_json="$(ve cloudidentity GetPortalLoginConfig --body '{}' 2>/dev/null || true)"
    status_json="$(ve cloudidentity GetServiceStatus --body '{}' 2>/dev/null || true)"

    CONFIG_JSON="$config_json" STATUS_JSON="$status_json" python3 <<'PY'
import json
import os


def result(raw):
    start = raw.find("{")
    if start == -1:
        return {}
    try:
        payload = json.loads(raw[start:])
    except json.JSONDecodeError:
        return {}
    return payload.get("Result", payload) or {}


config = result(os.environ.get("CONFIG_JSON", ""))
status = result(os.environ.get("STATUS_JSON", ""))

portal_url = str(config.get("PortalURL", "") or "").strip()
subdomain = str(config.get("Subdomain", "") or "").strip()

if not portal_url:
    instance_name = str(status.get("InstanceName", "") or "").strip()
    instance_id = str(status.get("InstanceId", "") or "").strip()
    if instance_name:
        subdomain = instance_name
        portal_url = f"https://{instance_name}.volccloudidentity.com"
    elif instance_id:
        subdomain = instance_id
        portal_url = f"https://{instance_id}.volccloudidentity.com"

login_url = f"{portal_url}/userportal" if portal_url else ""

print(json.dumps({
    "portal_url": portal_url,
    "subdomain": subdomain,
    "login_url": login_url,
}))
PY
  EOT
  ]

  depends_on = [null_resource.admin_password_reset]
}
