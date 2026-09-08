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
      version = ">= 0.0.41"
    }
  }
}

provider "volcenginecc" {
  region = var.region
}

locals {
  workspace_root             = abspath("${path.module}/../../..")
  identity_runtime_dir       = "${local.workspace_root}/landing-zone-setup/identity/${var.admin_username}"
  admin_password_result_path = "${local.identity_runtime_dir}/admin-password-reset.json"
  normalized_admin_email     = var.admin_email != null && trimspace(var.admin_email) != "" ? trimspace(var.admin_email) : null
  target_account_ids = toset(distinct(concat(
    [trimspace(var.management_account_id)],
    [for account_id in var.core_account_ids : trimspace(account_id) if trimspace(account_id) != ""]
  )))
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

      runtime_dir="${local.identity_runtime_dir}"
      result_file="${local.admin_password_result_path}"

      mkdir -p "$runtime_dir"

      ve cloudidentity ResetPassword --body '{
        "GenerateRandomPassword": true,
        "PasswordResetRequired": true,
        "UserId": "${volcenginecc_cloudidentity_user.admin.user_id}"
      }' > "$result_file"

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

    # Prefer GetPortalLoginConfig.PortalURL (authoritative full domain).
    config_json="$(ve cloudidentity GetPortalLoginConfig --body '{}' 2>/dev/null || true)"
    portal_url="$(printf '%s' "$config_json" \
      | sed -n 's/.*"PortalURL"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1)"
    subdomain="$(printf '%s' "$config_json" \
      | sed -n 's/.*"Subdomain"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1)"

    # Fallback to GetServiceStatus instance fields when portal config is unavailable.
    if [ -z "$portal_url" ]; then
      status_json="$(ve cloudidentity GetServiceStatus --body '{}' 2>/dev/null || true)"
      instance_name="$(printf '%s' "$status_json" \
        | sed -n 's/.*"InstanceName"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1)"
      instance_id="$(printf '%s' "$status_json" \
        | sed -n 's/.*"InstanceId"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1)"
      if [ -n "$instance_name" ]; then
        subdomain="$instance_name"
        portal_url="https://$instance_name.volccloudidentity.com"
      elif [ -n "$instance_id" ]; then
        subdomain="$instance_id"
        portal_url="https://$instance_id.volccloudidentity.com"
      fi
    fi

    # Build the user portal login entry; empty when nothing could be resolved.
    if [ -n "$portal_url" ]; then
      login_url="$portal_url/userportal"
    else
      login_url=""
    fi

    printf '{"portal_url":"%s","subdomain":"%s","login_url":"%s"}' \
      "$portal_url" "$subdomain" "$login_url"
  EOT
  ]

  depends_on = [null_resource.admin_password_reset]
}
