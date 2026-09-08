locals {
  audit_log_bucket_name       = "${var.prefix}-organization-audit-logs"
  organization_trail_name     = "${var.prefix}-org-trail"
  log_archive_assume_role_trn = "trn:iam::${var.log_archive_account_id}:role/OrganizationAccessControlRole"
  tos_openapi_region          = "cn-beijing"
  default_trail_event_sources = jsondecode(file("${path.module}/default-trail-event-sources.json"))
  effective_trail_event_sources = (
    var.trail_event_sources != null ? var.trail_event_sources : local.default_trail_event_sources
  )
  trail_event_sources_cli_args = join(" ", [
    for idx, source in local.effective_trail_event_sources : format("--EventSources.%d \"%s\"", idx + 1, source)
  ])
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
# - `EventSources.N` 只是接口文档里的数组占位写法，实际 CLI 传参必须展开成
#   `--EventSources.1 ... --EventSources.2 ...` 这类从 1 开始的自然数序号。
# ---------------------------------------------------------------

resource "null_resource" "organization_trail" {
  provisioner "local-exec" {
    interpreter = ["/bin/sh", "-c"]
    command     = <<-EOT
      set -eu

      assume_role_output="$(ve sts AssumeRole \
        --RoleTrn "${local.log_archive_assume_role_trn}" \
        --RoleSessionName "lz-log-setup")"

      temp_profile="lz-log-${var.log_archive_account_id}-create"
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
      printf '%s' "$caller_identity_output" | grep -q "${var.log_archive_account_id}" || {
        echo "temporary log execution identity probe did not match log archive account ${var.log_archive_account_id}" >&2
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
        "--access-key",
        credentials["AccessKeyId"],
        "--secret-key",
        credentials["SecretAccessKey"],
        "--session-token",
        credentials["SessionToken"],
    ],
    check=True,
    text=True,
    capture_output=True,
)
sys.stdout.write(completed.stdout)
sys.stderr.write(completed.stderr)
PY
      )" || {
        echo "failed to ensure TOS is activated in log archive account ${var.log_archive_account_id}" >&2
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

        if printf '%s' "$create_trail_output" | grep -Eqi '(^|[^0-9])500([^0-9]|$)|InternalError|ServiceUnavailable'; then
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
      printf '%s' "$describe_trails_output" | grep -q "\"TrailName\"[[:space:]]*:[[:space:]]*\"${local.organization_trail_name}\"" || {
        echo "DescribeTrails did not return expected trail ${local.organization_trail_name}" >&2
        printf '%s\n' "$describe_trails_output" >&2
        exit 1
      }
      printf '%s' "$describe_trails_output" | grep -q "\"TosBucketName\"[[:space:]]*:[[:space:]]*\"${local.audit_log_bucket_name}\"" || {
        echo "DescribeTrails did not return expected bucket ${local.audit_log_bucket_name}" >&2
        printf '%s\n' "$describe_trails_output" >&2
        exit 1
      }
    EOT
  }

  triggers = {
    log_archive_account_id = var.log_archive_account_id
    bucket_name            = local.audit_log_bucket_name
    trail_name             = local.organization_trail_name
    tos_openapi_region     = local.tos_openapi_region
    trail_event_sources    = jsonencode(local.effective_trail_event_sources)
  }
}

resource "null_resource" "enable_trail_logging" {
  provisioner "local-exec" {
    interpreter = ["/bin/sh", "-c"]
    command     = <<-EOT
      set -eu

      assume_role_output="$(ve sts AssumeRole \
        --RoleTrn "${local.log_archive_assume_role_trn}" \
        --RoleSessionName "lz-log-start-logging")"

      temp_profile="lz-log-${var.log_archive_account_id}-start"
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
      printf '%s' "$caller_identity_output" | grep -q "${var.log_archive_account_id}" || {
        echo "temporary log execution identity probe did not match log archive account ${var.log_archive_account_id}" >&2
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
      printf '%s' "$describe_trails_output" | grep -q "\"TrailName\"[[:space:]]*:[[:space:]]*\"${local.organization_trail_name}\"" || {
        echo "DescribeTrails did not return expected trail ${local.organization_trail_name}" >&2
        printf '%s\n' "$describe_trails_output" >&2
        exit 1
      }
      printf '%s' "$describe_trails_output" | grep -q "\"LoggingStatus\"[[:space:]]*:[[:space:]]*\"Enable\"" || {
        echo "DescribeTrails did not return expected logging status Enable" >&2
        printf '%s\n' "$describe_trails_output" >&2
        exit 1
      }
    EOT
  }

  triggers = {
    log_archive_account_id = var.log_archive_account_id
    trail_name             = local.organization_trail_name
  }

  depends_on = [null_resource.organization_trail]
}
