locals {
  landing_zone_context = var.landing_zone_context_path == null ? null : try(
    jsondecode(file(var.landing_zone_context_path)),
    null,
  )
  effective_log_archive_account_id = var.landing_zone_context_path != null ? try(
    local.landing_zone_context.phase_inputs.log.account_id == null ? "" : trimspace(tostring(local.landing_zone_context.phase_inputs.log.account_id)),
    "",
  ) : (var.log_archive_account_id == null ? "" : trimspace(var.log_archive_account_id))
  confirmed_architecture_path = var.landing_zone_context_path == null ? null : "${dirname(var.landing_zone_context_path)}/confirmed-architecture.json"
  architecture_hash_matches = var.landing_zone_context_path == null ? true : try(
    filesha256(local.confirmed_architecture_path) == local.landing_zone_context.configuration.architecture_sha256,
    false,
  )
  audit_log_bucket_name       = "${var.prefix}-organization-audit-logs"
  organization_trail_name     = "${var.prefix}-org-trail"
  log_archive_assume_role_trn = "trn:iam::${local.effective_log_archive_account_id}:role/OrganizationAccessControlRole"
  tos_openapi_region          = "cn-beijing"
  # 默认通过 CreateTrail 的 IncludeAllEventSources 采集全部事件源；仅当用户显式提供
  # trail_event_sources 收窄审计范围时，才关闭全量并逐个展开 --EventSources.N。
  trail_include_all_event_sources = var.trail_event_sources == null
  trail_event_sources_cli_args = local.trail_include_all_event_sources ? "--IncludeAllEventSources true" : join(" ", concat(
    ["--IncludeAllEventSources false"],
    [for idx, source in var.trail_event_sources : format("--EventSources.%d \"%s\"", idx + 1, source)],
  ))
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
    error_message = "The log phase prefix/region must match the confirmed Landing Zone context."
  }

  assert {
    condition     = local.architecture_hash_matches
    error_message = "confirmed-architecture.json does not match the architecture digest recorded in landing-zone-context.json."
  }

  assert {
    condition     = var.landing_zone_context_path == null ? true : try(local.landing_zone_context.phase_inputs.log.enabled, false)
    error_message = "The log capability is disabled in the confirmed Landing Zone design; skip Phase 04."
  }

  assert {
    condition     = local.effective_log_archive_account_id != ""
    error_message = "The log capability requires a non-empty log_archive account binding."
  }
}

check "legacy_log_input_compatibility" {
  assert {
    condition = (
      var.landing_zone_context_path == null ||
      var.log_archive_account_id == null ||
      trimspace(var.log_archive_account_id) == local.effective_log_archive_account_id
    )
    error_message = "log_archive_account_id conflicts with the authoritative Landing Zone context."
  }
}

# ---------------------------------------------------------------
# 通过日志归档账号的 OrganizationAccessControlRole 配置组织级操作审计 (CloudTrail)
# 说明：
# - `RegisterDelegatedAdministrator` 作为当前阶段的前置步骤，在 Terraform 之外由 ve CLI 完成；
#   本蓝图默认该前置条件已经满足，然后进入日志归档账号执行 CloudTrail 写操作。
# - 当前不再通过 provider 跨账号创建 TOS Bucket。
# - CreateTrail 前会先在日志归档账号上下文中通过 TOS OpenAPI 查询并补齐服务开通状态；
#   若账号当前处于欠费关停、欠费回收或已销户等状态，则停止本阶段并提示用户处理账号状态。
# - CreateTrail / StartLogging 必须在日志归档账号上下文中执行，不能直接落在当前管理员账号。
# - 由于 ve CLI 在本机已有 profile 时会优先使用 profile 鉴权，不能仅依赖 export STS 环境变量切换身份。
# - 当前改为：AssumeRole -> 写临时 log profile -> 在日志命令执行窗口内显式 --profile 调用 -> 删除临时 profile。
# - 默认使用 CreateTrail 的 IncludeAllEventSources=true 一次性采集全部事件源；
#   仅当用户显式提供 trail_event_sources 收窄范围时，才置为 false 并展开
#   `--EventSources.1 ... --EventSources.2 ...` 这类从 1 开始的自然数序号。
# ---------------------------------------------------------------

resource "null_resource" "organization_trail" {
  provisioner "local-exec" {
    interpreter = ["/bin/sh", "-c"]
    command     = <<-EOT
      set -eu

      # 结构化解析 DescribeTrails 响应：确认目标 trail 的某个字段等于期望值。
      trail_field_matches() {
        DESCRIBE_OUTPUT="$1" python3 - "$2" "$3" "$4" <<'PY'
import json
import os
import sys

trail_name = sys.argv[1]
field = sys.argv[2]
expected = sys.argv[3]
raw = os.environ.get("DESCRIBE_OUTPUT", "")
start = raw.find("{")
if start == -1:
    raise SystemExit(1)
try:
    payload = json.loads(raw[start:])
except json.JSONDecodeError:
    raise SystemExit(1)
for trail in payload.get("Result", {}).get("Trails", []) or []:
    if str(trail.get("TrailName", "")) == trail_name and str(trail.get(field, "")) == expected:
        raise SystemExit(0)
raise SystemExit(1)
PY
      }

      # 判断错误是否可重试：优先看结构化 ResponseMetadata.Error.Code，
      # 避免旧实现在整段输出里搜 "500" 时被 trail 名/RequestId 中的数字误伤。
      is_retryable_error() {
        ERROR_OUTPUT="$1" python3 - <<'PY'
import json
import os
import sys

raw = os.environ.get("ERROR_OUTPUT", "")
retryable = {"InternalError", "ServiceUnavailable"}
start = raw.find("{")
if start != -1:
    try:
        payload = json.loads(raw[start:])
    except json.JSONDecodeError:
        payload = None
    if payload is not None:
        code = payload.get("ResponseMetadata", {}).get("Error", {}).get("Code", "")
        raise SystemExit(0 if code in retryable else 1)
# 无法解析为结构化错误时，回退到保守的关键字判断（不含裸数字 500）。
raise SystemExit(0 if any(token in raw for token in retryable) else 1)
PY
      }

      assume_role_output="$(ve sts AssumeRole \
        --RoleTrn "${local.log_archive_assume_role_trn}" \
        --RoleSessionName "lz-log-setup")"

      temp_profile="lz-log-${local.effective_log_archive_account_id}-create"
      temp_home="$(mktemp -d -t lz-log-create-home.XXXXXX)"
      cleanup() {
        cleanup_status=$?
        if [ -n "$${temp_home:-}" ]; then
          rm -rf "$temp_home"
        fi
        exit "$cleanup_status"
      }
      trap cleanup EXIT INT TERM

      ASSUME_ROLE_OUTPUT="$assume_role_output" python3 - "$temp_profile" "$temp_home" "${var.region}" <<'PY'
import json
import os
import subprocess
import sys

profile = sys.argv[1]
home_dir = sys.argv[2]
region = sys.argv[3]
raw = os.environ["ASSUME_ROLE_OUTPUT"]
json_start = raw.find("{")
if json_start == -1:
    print("failed to assume log archive account role: no JSON payload found in AssumeRole response", file=sys.stderr)
    raise SystemExit(1)
payload = json.loads(raw[json_start:])
credentials = payload.get("Result", {}).get("Credentials", {})

if (
    not credentials.get("AccessKeyId")
    or not credentials.get("SecretAccessKey")
    or not credentials.get("SessionToken")
):
    print("failed to assume log archive account role: credentials not found in AssumeRole response", file=sys.stderr)
    raise SystemExit(1)

subprocess.run(
    [
        "ve",
        "configure",
        "set",
        "--profile",
        profile,
        "--region",
        region,
        "--access-key",
        credentials["AccessKeyId"],
        "--secret-key",
        credentials["SecretAccessKey"],
        "--session-token",
        credentials["SessionToken"],
    ],
    env={**os.environ, "HOME": home_dir},
    check=True,
    stdout=subprocess.DEVNULL,
)
PY
      caller_identity_output="$(HOME="$temp_home" ve sts GetCallerIdentity --profile "$temp_profile" 2>&1)" || {
        printf '%s\n' "$caller_identity_output" >&2
        exit 1
      }
      printf '%s' "$caller_identity_output" | grep -q "${local.effective_log_archive_account_id}" || {
        echo "temporary log execution identity probe did not match log archive account ${local.effective_log_archive_account_id}" >&2
        printf '%s\n' "$caller_identity_output" >&2
        exit 1
      }

      tos_activation_output="$(ASSUME_ROLE_OUTPUT="$assume_role_output" python3 - "${path.module}/tos_activate.py" "${local.tos_openapi_region}" <<'PY'
import json
import os
import subprocess
import sys

helper_path = sys.argv[1]
region = sys.argv[2]
raw = os.environ["ASSUME_ROLE_OUTPUT"]
json_start = raw.find("{")
if json_start == -1:
    print("failed to ensure TOS is activated in log archive account: no JSON payload found in AssumeRole response", file=sys.stderr)
    raise SystemExit(1)
payload = json.loads(raw[json_start:])
credentials = payload.get("Result", {}).get("Credentials", {})

if (
    not credentials.get("AccessKeyId")
    or not credentials.get("SecretAccessKey")
    or not credentials.get("SessionToken")
):
    print("failed to ensure TOS is activated in log archive account: credentials not found in AssumeRole response", file=sys.stderr)
    raise SystemExit(1)

completed = subprocess.run(
    [
        sys.executable,
        helper_path,
        "--region",
        region,
    ],
    check=True,
    text=True,
    capture_output=True,
    env={
        **os.environ,
        "VOLCENGINE_ACCESS_KEY": credentials["AccessKeyId"],
        "VOLCENGINE_SECRET_KEY": credentials["SecretAccessKey"],
        "VOLCENGINE_SESSION_TOKEN": credentials["SessionToken"],
    },
)
sys.stdout.write(completed.stdout)
sys.stderr.write(completed.stderr)
PY
      )" || {
        echo "failed to ensure TOS is activated in log archive account ${local.effective_log_archive_account_id}" >&2
        printf '%s\n' "$tos_activation_output" >&2
        exit 1
      }
      printf '%s\n' "$tos_activation_output"

      create_trail_succeeded="false"
      for attempt in 1 2 3 4 5 6; do
        create_trail_output="$(HOME="$temp_home" ve cloudtrail20180101 CreateTrail \
          --profile "$temp_profile" \
          --TrailName "${local.organization_trail_name}" \
          --TrailType 1 \
          --EventRW "All" \
          ${local.trail_event_sources_cli_args} \
          --TosBucketName "${local.audit_log_bucket_name}" \
          --TosBucketRegion "${var.region}" \
          --TosKeyPrefix "cloudtrail" 2>&1)" && {
          create_trail_succeeded="true"
          break
        }

        if is_retryable_error "$create_trail_output"; then
          if [ "$attempt" -lt 6 ]; then
            sleep 5
            continue
          fi
        fi

        echo "failed to create organization trail ${local.organization_trail_name}" >&2
        printf '%s\n' "$create_trail_output" >&2
        exit 1
      done
      [ "$create_trail_succeeded" = "true" ] || {
        echo "failed to create organization trail ${local.organization_trail_name} after retries" >&2
        printf '%s\n' "$create_trail_output" >&2
        exit 1
      }

      describe_trails_output="$(HOME="$temp_home" ve cloudtrail20180101 DescribeTrails \
        --profile "$temp_profile" \
        --TrailNames.1 "${local.organization_trail_name}" \
        --IncludeOrganizationTrail 1 2>&1)" || {
        printf '%s\n' "$describe_trails_output" >&2
        exit 1
      }
      trail_field_matches "$describe_trails_output" "${local.organization_trail_name}" "TrailName" "${local.organization_trail_name}" || {
        echo "DescribeTrails did not return expected trail ${local.organization_trail_name}" >&2
        printf '%s\n' "$describe_trails_output" >&2
        exit 1
      }
      trail_field_matches "$describe_trails_output" "${local.organization_trail_name}" "TosBucketName" "${local.audit_log_bucket_name}" || {
        echo "DescribeTrails did not return expected bucket ${local.audit_log_bucket_name}" >&2
        printf '%s\n' "$describe_trails_output" >&2
        exit 1
      }
    EOT
  }

  triggers = {
    log_archive_account_id    = local.effective_log_archive_account_id
    bucket_name               = local.audit_log_bucket_name
    trail_name                = local.organization_trail_name
    tos_openapi_region        = local.tos_openapi_region
    include_all_event_sources = local.trail_include_all_event_sources
    trail_event_sources       = jsonencode(var.trail_event_sources == null ? [] : var.trail_event_sources)
  }
}

resource "null_resource" "enable_trail_logging" {
  provisioner "local-exec" {
    interpreter = ["/bin/sh", "-c"]
    command     = <<-EOT
      set -eu

      # 结构化解析 DescribeTrails 响应：确认目标 trail 的某个字段等于期望值。
      trail_field_matches() {
        DESCRIBE_OUTPUT="$1" python3 - "$2" "$3" "$4" <<'PY'
import json
import os
import sys

trail_name = sys.argv[1]
field = sys.argv[2]
expected = sys.argv[3]
raw = os.environ.get("DESCRIBE_OUTPUT", "")
start = raw.find("{")
if start == -1:
    raise SystemExit(1)
try:
    payload = json.loads(raw[start:])
except json.JSONDecodeError:
    raise SystemExit(1)
for trail in payload.get("Result", {}).get("Trails", []) or []:
    if str(trail.get("TrailName", "")) == trail_name and str(trail.get(field, "")) == expected:
        raise SystemExit(0)
raise SystemExit(1)
PY
      }

      assume_role_output="$(ve sts AssumeRole \
        --RoleTrn "${local.log_archive_assume_role_trn}" \
        --RoleSessionName "lz-log-start-logging")"

      temp_profile="lz-log-${local.effective_log_archive_account_id}-start"
      temp_home="$(mktemp -d -t lz-log-start-home.XXXXXX)"
      cleanup() {
        cleanup_status=$?
        if [ -n "$${temp_home:-}" ]; then
          rm -rf "$temp_home"
        fi
        exit "$cleanup_status"
      }
      trap cleanup EXIT INT TERM

      ASSUME_ROLE_OUTPUT="$assume_role_output" python3 - "$temp_profile" "$temp_home" "${var.region}" <<'PY'
import json
import os
import subprocess
import sys

profile = sys.argv[1]
home_dir = sys.argv[2]
region = sys.argv[3]
raw = os.environ["ASSUME_ROLE_OUTPUT"]
json_start = raw.find("{")
if json_start == -1:
    print("failed to assume log archive account role: no JSON payload found in AssumeRole response", file=sys.stderr)
    raise SystemExit(1)
payload = json.loads(raw[json_start:])
credentials = payload.get("Result", {}).get("Credentials", {})

if (
    not credentials.get("AccessKeyId")
    or not credentials.get("SecretAccessKey")
    or not credentials.get("SessionToken")
):
    print("failed to assume log archive account role: credentials not found in AssumeRole response", file=sys.stderr)
    raise SystemExit(1)

subprocess.run(
    [
        "ve",
        "configure",
        "set",
        "--profile",
        profile,
        "--region",
        region,
        "--access-key",
        credentials["AccessKeyId"],
        "--secret-key",
        credentials["SecretAccessKey"],
        "--session-token",
        credentials["SessionToken"],
    ],
    env={**os.environ, "HOME": home_dir},
    check=True,
    stdout=subprocess.DEVNULL,
)
PY
      caller_identity_output="$(HOME="$temp_home" ve sts GetCallerIdentity --profile "$temp_profile" 2>&1)" || {
        printf '%s\n' "$caller_identity_output" >&2
        exit 1
      }
      printf '%s' "$caller_identity_output" | grep -q "${local.effective_log_archive_account_id}" || {
        echo "temporary log execution identity probe did not match log archive account ${local.effective_log_archive_account_id}" >&2
        printf '%s\n' "$caller_identity_output" >&2
        exit 1
      }

      HOME="$temp_home" ve cloudtrail20180101 StartLogging \
        --profile "$temp_profile" \
        --TrailName "${local.organization_trail_name}"

      describe_trails_output="$(HOME="$temp_home" ve cloudtrail20180101 DescribeTrails \
        --profile "$temp_profile" \
        --TrailNames.1 "${local.organization_trail_name}" \
        --IncludeOrganizationTrail 1 2>&1)" || {
        printf '%s\n' "$describe_trails_output" >&2
        exit 1
      }
      trail_field_matches "$describe_trails_output" "${local.organization_trail_name}" "TrailName" "${local.organization_trail_name}" || {
        echo "DescribeTrails did not return expected trail ${local.organization_trail_name}" >&2
        printf '%s\n' "$describe_trails_output" >&2
        exit 1
      }
      trail_field_matches "$describe_trails_output" "${local.organization_trail_name}" "LoggingStatus" "Enable" || {
        echo "DescribeTrails did not return expected logging status Enable" >&2
        printf '%s\n' "$describe_trails_output" >&2
        exit 1
      }
    EOT
  }

  triggers = {
    log_archive_account_id = local.effective_log_archive_account_id
    trail_name             = local.organization_trail_name
  }

  depends_on = [null_resource.organization_trail]
}
