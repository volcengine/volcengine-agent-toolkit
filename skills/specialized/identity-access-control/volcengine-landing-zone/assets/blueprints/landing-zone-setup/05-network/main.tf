terraform {
  required_providers {
    volcenginecc = {
      source  = "volcengine/volcenginecc"
      version = ">= 0.0.41"
    }
  }
}

locals {
  network_account_assume_role_trn    = "trn:iam::${var.network_account_id}:role/OrganizationAccessControlRole"
  resource_share_service_principal   = "resource_share"
  transit_router_resource_share_name = "${var.prefix}-shared-tr-${var.region}"
  transit_router_resource_trn        = "trn:transitrouter:${var.region}:${var.network_account_id}:transitrouter/${volcenginecc_transitrouter_transit_router.this.id}"
  network_availability_zone_a        = coalesce(var.network_availability_zone_a, "${var.region}-a")
  network_availability_zone_b        = coalesce(var.network_availability_zone_b, "${var.region}-b")
  nat_gateway_name                   = coalesce(var.nat_gateway_name, "${var.prefix}-nat")
  nat_eip_name                       = coalesce(var.eip_name, "${var.prefix}-nat-eip")
  nat_snat_entry_name                = coalesce(var.snat_entry_name, "${var.prefix}-default-snat")
  tr_route_table_dmz_public_name     = "RT_DMZ_Public"
  tr_route_table_egress_name         = "RT_Egress_To_Internal"
}

# --- Provider: 主账号 (默认) ---
provider "volcenginecc" {
  region = var.region
}

# --- Provider: 网络账号 (通过 assume_role 跨账号) ---
provider "volcenginecc" {
  alias  = "network_account"
  region = var.region

  endpoints = {
    sts = "sts.volcengineapi.com"
  }

  assume_role = {
    assume_role_trn              = local.network_account_assume_role_trn
    assume_role_session_name     = "lz-network-setup"
    assume_role_duration_seconds = 3600
  }
}

# ---------------------------------------------------------------
# Part 1: 中转路由器 (Transit Router) — 在网络账号中创建
# ---------------------------------------------------------------
resource "volcenginecc_transitrouter_transit_router" "this" {
  provider = volcenginecc.network_account

  transit_router_name = "${var.prefix}-tr-${var.region}"
  description         = "Landing Zone Transit Router in network account for ${var.region}"
  project_name        = "default"

  tags = [
    {
      key   = "ManagedBy"
      value = "LandingZone"
    }
  ]

  depends_on = [null_resource.resource_share_organization_enabled]
}

# ---------------------------------------------------------------
# Part 1.4: 在组织管理员上下文中校验当前 ve 登录态确实属于目标管理账号
# 说明：
# - `RegisterDelegatedAdministrator` 与 `EnableSharingWithOrganization` 都直接使用当前 ve 登录态。
# - 在执行任何组织级写操作前，先用 GetCallerIdentity 校验当前登录态的账号 ID，避免误在错误组织上下文中执行。
# ---------------------------------------------------------------
resource "null_resource" "management_account_identity_probe" {
  provisioner "local-exec" {
    interpreter = ["/bin/sh", "-c"]
    command     = <<-EOT
      set -eu

      caller_identity_output="$(ve sts GetCallerIdentity 2>&1)" || {
        printf '%s\n' "$caller_identity_output" >&2
        exit 1
      }

      printf '%s' "$caller_identity_output" | grep -q "${var.management_account_id}" || {
        echo "current ve login identity did not match expected management account ${var.management_account_id}" >&2
        printf '%s\n' "$caller_identity_output" >&2
        exit 1
      }

      printf '%s\n' "$caller_identity_output"
    EOT
  }

  triggers = {
    management_account_id = var.management_account_id
  }
}

# ---------------------------------------------------------------
# Part 1.5: 将 resource_share 可信服务委派给网络账号
# 说明：
# - 该步骤必须在组织管理员上下文中执行，与 04-log 中委派审计管理员的模式保持一致。
# - 后续网络账号会以 resource_share 代理账号身份开启组织内共享并创建共享单元。
# ---------------------------------------------------------------
resource "null_resource" "resource_share_trusted_service_delegated_administrator" {
  provisioner "local-exec" {
    interpreter = ["/bin/sh", "-c"]
    command     = <<-EOT
      set -eu

      register_body=$(cat <<'JSON'
{"AccountId":"${var.network_account_id}","ServicePrincipal":"${local.resource_share_service_principal}"}
JSON
      )

      register_output=""
      if register_output=$(ve organization RegisterDelegatedAdministrator --body "$register_body" 2>&1); then
        :
      elif printf '%s' "$register_output" | grep -Eqi 'already exists|duplicate|重复|已存在|ExistDelegateAdministrator|DelegateAdministrator'; then
        :
      else
        echo "failed to register delegated administrator for trusted service ${local.resource_share_service_principal}" >&2
        printf '%s\n' "$register_output" >&2
        exit 1
      fi

      printf '%s\n' "$register_output"
    EOT
  }

  triggers = {
    network_account_id        = var.network_account_id
    trusted_service_principal = local.resource_share_service_principal
  }

  depends_on = [null_resource.management_account_identity_probe]
}

# ---------------------------------------------------------------
# Part 1.6: 在组织管理员上下文中启用企业组织共享能力
# 说明：
# - EnableSharingWithOrganization 属于组织级开关，必须在组织管理员上下文中执行。
# - 该开关由 05-network 一次性准备，后续账号工厂只更新共享范围，不再重复开启。
# ---------------------------------------------------------------
resource "null_resource" "resource_share_organization_enabled" {
  provisioner "local-exec" {
    interpreter = ["/bin/sh", "-c"]
    command     = <<-EOT
      set -eu

      enable_sharing_output=""
      if enable_sharing_output="$(ve resourceshare EnableSharingWithOrganization 2>&1)"; then
        :
      elif printf '%s' "$enable_sharing_output" | grep -Eqi 'already enabled|duplicate|重复|已开启|ShareWithOrganizationAlreadyEnabled'; then
        :
      else
        echo "failed to enable resource share with organization in management account context" >&2
        printf '%s\n' "$enable_sharing_output" >&2
        exit 1
      fi

      printf '%s\n' "$enable_sharing_output"
    EOT
  }

  triggers = {
    network_account_id        = var.network_account_id
    trusted_service_principal = local.resource_share_service_principal
  }

  depends_on = [null_resource.resource_share_trusted_service_delegated_administrator]
}

# ---------------------------------------------------------------
# Part 1.7: 在网络账号中创建可复用的 TR 共享单元
# 说明：
# - 资源共享单元的创建与关联在网络账号上下文中执行；此处显式 AssumeRole + 临时 profile，避免 ve CLI 落回默认身份。
# - 05-network 仅创建共享单元并关联 TR 资源；成员账号范围由账号工厂基线后续逐个追加。
# ---------------------------------------------------------------
resource "null_resource" "transit_router_resource_share" {
  provisioner "local-exec" {
    interpreter = ["/bin/sh", "-c"]
    command     = <<-EOT
      set -eu

      assume_role_output="$(ve sts AssumeRole \
        --RoleTrn "${local.network_account_assume_role_trn}" \
        --RoleSessionName "lz-network-rs-share")"

      temp_profile="lz-network-rs-${var.network_account_id}"
      temp_home="$(mktemp -d -t lz-network-rs-home.XXXXXX)"
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
    print("failed to assume network account role: no JSON payload found in AssumeRole response", file=sys.stderr)
    raise SystemExit(1)
payload = json.loads(raw[json_start:])
credentials = payload.get("Result", {}).get("Credentials", {})

if (
    not credentials.get("AccessKeyId")
    or not credentials.get("SecretAccessKey")
    or not credentials.get("SessionToken")
):
    print("failed to assume network account role: credentials not found in AssumeRole response", file=sys.stderr)
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
      printf '%s' "$caller_identity_output" | grep -q "${var.network_account_id}" || {
        echo "temporary network resource-share execution identity probe did not match network account ${var.network_account_id}" >&2
        printf '%s\n' "$caller_identity_output" >&2
        exit 1
      }

      describe_shares_output="$(HOME="$temp_home" ve resourceshare DescribeResourceShares \
        --profile "$temp_profile" \
        --Name "${local.transit_router_resource_share_name}" \
        --ResourceOwner SELF 2>&1)" || {
        printf '%s\n' "$describe_shares_output" >&2
        exit 1
      }

      resource_share_trn="$(DESCRIBE_SHARES_OUTPUT="$describe_shares_output" python3 - "${local.transit_router_resource_share_name}" <<'PY'
import json
import os
import sys

share_name = sys.argv[1]
payload = json.loads(os.environ["DESCRIBE_SHARES_OUTPUT"])
shares = payload.get("Result", {}).get("ResourceShares", [])

def recency_key(share, index):
    for field in ("UpdateTime", "UpdatedAt", "ModifyTime", "ModifiedAt", "CreateTime", "CreatedAt"):
        value = share.get(field)
        if value is not None and str(value).strip():
            return (str(value).strip(), index)
    return ("", index)

matching_shares = [
    (index, share)
    for index, share in enumerate(shares)
    if share.get("ResourceShareName") == share_name
]

active_shares = [
    (index, share)
    for index, share in matching_shares
    if share.get("Status", "") == "ACTIVE"
]
if active_shares:
    _, selected_share = max(active_shares, key=lambda item: recency_key(item[1], item[0]))
    print(selected_share.get("ResourceShareTrn", "").strip())
    raise SystemExit(0)

blocking_statuses = sorted(
    {
        share.get("Status", "").strip() or "<empty>"
        for _, share in matching_shares
        if share.get("Status", "") not in ("", "DELETED")
    }
)
if blocking_statuses:
    print(
        f"resource share {share_name} exists but has no ACTIVE record; blocking statuses: {', '.join(blocking_statuses)}",
        file=sys.stderr,
    )
    raise SystemExit(1)

print("")
PY
      )"

      if [ -z "$resource_share_trn" ]; then
        create_share_output="$(HOME="$temp_home" ve resourceshare CreateResourceShare \
          --profile "$temp_profile" \
          --Name "${local.transit_router_resource_share_name}" \
          --AllowShareType ORG 2>&1)" || {
          printf '%s\n' "$create_share_output" >&2
          exit 1
        }

        resource_share_trn="$(CREATE_SHARE_OUTPUT="$create_share_output" python3 - <<'PY'
import json
import os
import sys

payload = json.loads(os.environ["CREATE_SHARE_OUTPUT"])
resource_share_trn = payload.get("Result", {}).get("ResourceShareTrn", "").strip()
if not resource_share_trn:
    print("CreateResourceShare did not return ResourceShareTrn", file=sys.stderr)
    raise SystemExit(1)
print(resource_share_trn)
PY
        )"
      fi

      associate_resource_output=""
      if associate_resource_output="$(HOME="$temp_home" ve resourceshare AssociateResourceShare \
        --profile "$temp_profile" \
        --ResourceShareTrn "$resource_share_trn" \
        --ResourceTrns "${local.transit_router_resource_trn}" 2>&1)"; then
        :
      elif printf '%s' "$associate_resource_output" | grep -Eqi 'DuplicatedAssociation|ResourceConflict|already exist|重复|已存在'; then
        :
      else
        echo "failed to associate transit router resource ${local.transit_router_resource_trn} into resource share $resource_share_trn" >&2
        printf '%s\n' "$associate_resource_output" >&2
        exit 1
      fi

      resource_associated="false"
      for attempt in 1 2 3 4 5 6; do
        resource_associations_output="$(HOME="$temp_home" ve resourceshare ListResourceShareAssociations \
          --profile "$temp_profile" \
          --ResourceShareTrn "$resource_share_trn" \
          --AssociationType RESOURCE 2>&1)" || {
          printf '%s\n' "$resource_associations_output" >&2
          exit 1
        }
        if RESOURCE_ASSOCIATIONS_OUTPUT="$resource_associations_output" python3 - "${local.transit_router_resource_trn}" <<'PY'
import json
import os
import sys

target = sys.argv[1]
payload = json.loads(os.environ["RESOURCE_ASSOCIATIONS_OUTPUT"])
for association in payload.get("Result", {}).get("Associations", []):
    if association.get("AssociationEntity") == target and association.get("Status") == "ASSOCIATED":
        raise SystemExit(0)
raise SystemExit(1)
PY
        then
          resource_associated="true"
          break
        fi
        sleep 5
      done
      [ "$resource_associated" = "true" ] || {
        echo "transit router resource ${local.transit_router_resource_trn} is not ASSOCIATED in the resource share after waiting" >&2
        printf '%s\n' "$resource_associations_output" >&2
        exit 1
      }

      printf '%s\n' "resource share ready: $resource_share_trn"
    EOT
  }

  triggers = {
    resource_share_name         = local.transit_router_resource_share_name
    transit_router_resource_trn = local.transit_router_resource_trn
    network_account_id          = var.network_account_id
  }

  depends_on = [
    volcenginecc_transitrouter_transit_router.this,
    null_resource.resource_share_organization_enabled,
  ]
}

# ---------------------------------------------------------------
# Part 2: 网络底座 VPC — 在网络账号中创建
resource "volcenginecc_vpc_vpc" "network" {
  provider = volcenginecc.network_account

  cidr_block  = var.network_vpc_cidr
  vpc_name    = "${var.prefix}-network-vpc"
  description = "Network baseline VPC for Landing Zone"

  depends_on = [null_resource.resource_share_organization_enabled]
}

resource "volcenginecc_vpc_subnet" "network_az_a" {
  provider = volcenginecc.network_account

  vpc_id      = volcenginecc_vpc_vpc.network.id
  zone_id     = local.network_availability_zone_a
  cidr_block  = var.network_subnet_cidr_az_a
  subnet_name = "${var.prefix}-network-subnet-a"
}

resource "volcenginecc_vpc_subnet" "network_az_b" {
  provider = volcenginecc.network_account

  vpc_id      = volcenginecc_vpc_vpc.network.id
  zone_id     = local.network_availability_zone_b
  cidr_block  = var.network_subnet_cidr_az_b
  subnet_name = "${var.prefix}-network-subnet-b"

  depends_on = [volcenginecc_vpc_subnet.network_az_a]
}

# ---------------------------------------------------------------
# Part 2.4: 确保网络账号已具备 NAT Gateway 服务关联角色
# 说明：
# - NAT 在创建公网网关前需要网络账号内的 ServiceRoleForNatGateway。
# - 当前通过 ve CLI 在 assume_role 到网络账号后进行幂等创建；写隔离临时 HOME 并显式 --profile，避免 ve CLI 污染本机默认身份。
# ---------------------------------------------------------------
resource "null_resource" "network_account_natgateway_service_linked_role" {
  count = var.create_nat ? 1 : 0

  triggers = {
    network_account_id = var.network_account_id
    region             = var.region
  }

  provisioner "local-exec" {
    interpreter = ["/bin/sh", "-c"]
    command     = <<-EOT
      set -eu

      assume_role_output="$(ve sts AssumeRole \
        --RoleTrn "${local.network_account_assume_role_trn}" \
        --RoleSessionName "lz-network-nat-slr")"

      temp_profile="lz-network-nat-slr-${var.network_account_id}"
      temp_home="$(mktemp -d -t lz-network-nat-slr-home.XXXXXX)"
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
    print("failed to assume network account role: no JSON payload found in AssumeRole response", file=sys.stderr)
    raise SystemExit(1)
payload = json.loads(raw[json_start:])
credentials = payload.get("Result", {}).get("Credentials", {})

if (
    not credentials.get("AccessKeyId")
    or not credentials.get("SecretAccessKey")
    or not credentials.get("SessionToken")
):
    print("failed to assume network account role: credentials not found in AssumeRole response", file=sys.stderr)
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
      identity="$(HOME="$temp_home" ve sts GetCallerIdentity --profile "$temp_profile" 2>&1)" || {
        echo "$identity" >&2
        exit 1
      }
      printf '%s' "$identity" | grep -q "${var.network_account_id}" || {
        echo "temporary network nat slr execution identity probe did not match network account ${var.network_account_id}" >&2
        printf '%s\n' "$identity" >&2
        exit 1
      }

      create_out="$(HOME="$temp_home" ve iam CreateServiceLinkedRole --profile "$temp_profile" --ServiceName natgateway 2>&1)" && exit 0
      printf '%s' "$create_out" | grep -Eqi 'RoleAlreadyExists|already exists|重复|已存在' && exit 0
      printf '%s\n' "$create_out" >&2
      exit 1
    EOT
  }

  depends_on = [null_resource.resource_share_organization_enabled]
}

# ---------------------------------------------------------------
# Part 2.5: 在网络底座中创建统一公网出向能力
# 说明：
# - 参考网络工程师方案，在网络账号内补齐 NAT、EIP 与 SNAT，提供统一公网南北出向能力。
# - 本阶段只建设共享网络出口，不引入业务入口层 ALB 规则。
# ---------------------------------------------------------------
resource "volcenginecc_natgateway_ngw" "network_public_egress" {
  count    = var.create_nat ? 1 : 0
  provider = volcenginecc.network_account

  vpc_id           = volcenginecc_vpc_vpc.network.id
  subnet_id        = volcenginecc_vpc_subnet.network_az_a.id
  nat_gateway_name = local.nat_gateway_name
  description      = "Landing Zone shared public egress NAT gateway"
  spec             = var.nat_spec
  billing_type     = 2
  network_type     = var.nat_network_type
  project_name     = "default"

  tags = [
    {
      key   = "ManagedBy"
      value = "LandingZone"
    }
  ]

  depends_on = [
    volcenginecc_vpc_subnet.network_az_b,
    null_resource.network_account_natgateway_service_linked_role,
  ]
}

resource "volcenginecc_vpc_eip" "network_nat" {
  count    = var.create_nat ? 1 : 0
  provider = volcenginecc.network_account

  name          = local.nat_eip_name
  description   = "Landing Zone shared public egress EIP"
  isp           = var.eip_isp
  billing_type  = var.eip_billing_type
  bandwidth     = var.eip_bandwidth
  period        = var.eip_period
  project_name  = "default"
  instance_id   = volcenginecc_natgateway_ngw.network_public_egress[0].nat_gateway_id
  instance_type = "Nat"
  direct_mode   = var.eip_direct_mode

  tags = [
    {
      key   = "ManagedBy"
      value = "LandingZone"
    }
  ]

  depends_on = [volcenginecc_natgateway_ngw.network_public_egress]
}

resource "volcenginecc_natgateway_snatentry" "network_public_egress" {
  count    = var.create_nat ? 1 : 0
  provider = volcenginecc.network_account

  nat_gateway_id  = volcenginecc_natgateway_ngw.network_public_egress[0].nat_gateway_id
  snat_entry_name = local.nat_snat_entry_name
  source_cidr     = var.snat_source_cidr
  eip_id          = volcenginecc_vpc_eip.network_nat[0].allocation_id

  depends_on = [volcenginecc_vpc_eip.network_nat]
}

# ---------------------------------------------------------------
# Part 2.6: 确保网络账号已具备 Transit Router 服务关联角色
# 说明：
# - TR 在创建 VPC attachment 时需要网络账号内的 ServiceRoleForTransitRouter。
# - 当前通过 ve CLI 在 assume_role 到网络账号后进行幂等创建；写隔离临时 HOME 并显式 --profile，避免 ve CLI 污染本机默认身份。
# ---------------------------------------------------------------
resource "null_resource" "network_account_transitrouter_service_linked_role" {
  triggers = {
    network_account_id = var.network_account_id
    region             = var.region
  }

  provisioner "local-exec" {
    interpreter = ["/bin/sh", "-c"]
    command     = <<-EOT
      set -eu

      assume_role_output="$(ve sts AssumeRole \
        --RoleTrn "${local.network_account_assume_role_trn}" \
        --RoleSessionName "lz-network-slr")"

      temp_profile="lz-network-slr-${var.network_account_id}"
      temp_home="$(mktemp -d -t lz-network-slr-home.XXXXXX)"
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
    print("failed to assume network account role: no JSON payload found in AssumeRole response", file=sys.stderr)
    raise SystemExit(1)
payload = json.loads(raw[json_start:])
credentials = payload.get("Result", {}).get("Credentials", {})

if (
    not credentials.get("AccessKeyId")
    or not credentials.get("SecretAccessKey")
    or not credentials.get("SessionToken")
):
    print("failed to assume network account role: credentials not found in AssumeRole response", file=sys.stderr)
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
      identity="$(HOME="$temp_home" ve sts GetCallerIdentity --profile "$temp_profile" 2>&1)" || {
        echo "$identity" >&2
        exit 1
      }
      printf '%s' "$identity" | grep -q "${var.network_account_id}" || {
        echo "temporary network slr execution identity probe did not match network account ${var.network_account_id}" >&2
        printf '%s\n' "$identity" >&2
        exit 1
      }

      create_out="$(HOME="$temp_home" ve iam CreateServiceLinkedRole --profile "$temp_profile" --ServiceName transitrouter 2>&1)" && exit 0
      printf '%s' "$create_out" | grep -Eqi 'RoleAlreadyExists|already exists|重复|已存在' && exit 0
      printf '%s\n' "$create_out" >&2
      exit 1
    EOT
  }

  depends_on = [null_resource.resource_share_organization_enabled]
}

# ---------------------------------------------------------------
# Part 3: 将网络底座 VPC 连接到中转路由器
# ---------------------------------------------------------------
resource "volcenginecc_transitrouter_vpc_attachment" "network" {
  provider = volcenginecc.network_account

  transit_router_id              = volcenginecc_transitrouter_transit_router.this.id
  vpc_id                         = volcenginecc_vpc_vpc.network.id
  transit_router_attachment_name = "${var.prefix}-network-attach"
  description                    = "Network baseline VPC attachment"
  auto_publish_route_enabled     = true

  attach_points = [
    {
      subnet_id = volcenginecc_vpc_subnet.network_az_a.id
      zone_id   = local.network_availability_zone_a
    },
    {
      subnet_id = volcenginecc_vpc_subnet.network_az_b.id
      zone_id   = local.network_availability_zone_b
    }
  ]

  tags = [
    {
      key   = "ManagedBy"
      value = "LandingZone"
    }
  ]

  depends_on = [null_resource.network_account_transitrouter_service_linked_role]
}

# ---------------------------------------------------------------
# Part 4: 预创建中心 TR 的共享路由表骨架
# 说明：
# - 中心 TR 的共享路由策略由网络底座持有，避免后续每个账号基线 run 去争抢共享路由表本体。
# - 网络底座 attachment 视为统一公网出口 / DMZ 方向的下一跳。
# ---------------------------------------------------------------
resource "null_resource" "network_account_transit_router_route_tables" {
  triggers = {
    network_account_id          = var.network_account_id
    region                      = var.region
    transit_router_id           = volcenginecc_transitrouter_transit_router.this.id
    network_vpc_attachment_id   = volcenginecc_transitrouter_vpc_attachment.network.transit_router_attachment_id
    dmz_public_route_table_name = local.tr_route_table_dmz_public_name
    egress_route_table_name     = local.tr_route_table_egress_name
  }

  provisioner "local-exec" {
    interpreter = ["/bin/sh", "-c"]
    command     = <<-EOT
      set -eu

      assume_role_output="$(ve sts AssumeRole \
        --RoleTrn "${local.network_account_assume_role_trn}" \
        --RoleSessionName "lz-network-tr-route")"

      temp_profile="lz-network-tr-route-${var.network_account_id}"
      temp_home="$(mktemp -d -t lz-network-tr-route-home.XXXXXX)"
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
    print("failed to assume network account role: no JSON payload found in AssumeRole response", file=sys.stderr)
    raise SystemExit(1)
payload = json.loads(raw[json_start:])
credentials = payload.get("Result", {}).get("Credentials", {})

if (
    not credentials.get("AccessKeyId")
    or not credentials.get("SecretAccessKey")
    or not credentials.get("SessionToken")
):
    print("failed to assume network account role: credentials not found in AssumeRole response", file=sys.stderr)
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
      identity="$(HOME="$temp_home" ve sts GetCallerIdentity --profile "$temp_profile" 2>&1)" || {
        echo "$identity" >&2
        exit 1
      }
      printf '%s' "$identity" | grep -q "${var.network_account_id}" || {
        echo "temporary network transit router route execution identity probe did not match network account ${var.network_account_id}" >&2
        printf '%s\n' "$identity" >&2
        exit 1
      }

      route_tables_output="$(HOME="$temp_home" ve transitrouter DescribeTransitRouterRouteTables \
        --profile "$temp_profile" \
        --TransitRouterId "${volcenginecc_transitrouter_transit_router.this.id}" 2>&1)" || {
        printf '%s\n' "$route_tables_output" >&2
        exit 1
      }

      route_table_ids="$(ROUTE_TABLES_OUTPUT="$route_tables_output" python3 - "${local.tr_route_table_dmz_public_name}" "${local.tr_route_table_egress_name}" <<'PY'
import json
import os
import sys

dmz_name = sys.argv[1]
egress_name = sys.argv[2]
payload = json.loads(os.environ["ROUTE_TABLES_OUTPUT"])
tables = payload.get("Result", {}).get("TransitRouterRouteTables")
if tables is None:
    tables = payload.get("Result", {}).get("RouteTables", [])

result = {}
for table in tables or []:
    name = (table.get("TransitRouterRouteTableName") or table.get("RouteTableName") or "").strip()
    table_id = (table.get("TransitRouterRouteTableId") or table.get("RouteTableId") or "").strip()
    if name and table_id:
        result[name] = table_id

print(result.get(dmz_name, ""))
print(result.get(egress_name, ""))
PY
      )"

      dmz_route_table_id="$(printf '%s\n' "$route_table_ids" | sed -n '1p')"
      egress_route_table_id="$(printf '%s\n' "$route_table_ids" | sed -n '2p')"

      if [ -z "$dmz_route_table_id" ]; then
        create_dmz_output="$(HOME="$temp_home" ve transitrouter CreateTransitRouterRouteTable \
          --profile "$temp_profile" \
          --TransitRouterId "${volcenginecc_transitrouter_transit_router.this.id}" \
          --TransitRouterRouteTableName "${local.tr_route_table_dmz_public_name}" \
          --Description "DMZ public route table" 2>&1)" || {
          printf '%s\n' "$create_dmz_output" >&2
          exit 1
        }
        dmz_route_table_id="$(CREATE_DMZ_OUTPUT="$create_dmz_output" python3 - <<'PY'
import json
import os
import sys

payload = json.loads(os.environ["CREATE_DMZ_OUTPUT"])
result = payload.get("Result", {})
value = (result.get("TransitRouterRouteTableId") or result.get("RouteTableId") or "").strip()
if not value:
    print("CreateTransitRouterRouteTable did not return DMZ route table id", file=sys.stderr)
    raise SystemExit(1)
print(value)
PY
        )"
      fi

      if [ -z "$egress_route_table_id" ]; then
        create_egress_output="$(HOME="$temp_home" ve transitrouter CreateTransitRouterRouteTable \
          --profile "$temp_profile" \
          --TransitRouterId "${volcenginecc_transitrouter_transit_router.this.id}" \
          --TransitRouterRouteTableName "${local.tr_route_table_egress_name}" \
          --Description "Internal egress route table" 2>&1)" || {
          printf '%s\n' "$create_egress_output" >&2
          exit 1
        }
        egress_route_table_id="$(CREATE_EGRESS_OUTPUT="$create_egress_output" python3 - <<'PY'
import json
import os
import sys

payload = json.loads(os.environ["CREATE_EGRESS_OUTPUT"])
result = payload.get("Result", {})
value = (result.get("TransitRouterRouteTableId") or result.get("RouteTableId") or "").strip()
if not value:
    print("CreateTransitRouterRouteTable did not return egress route table id", file=sys.stderr)
    raise SystemExit(1)
print(value)
PY
        )"
      fi

      [ -n "$dmz_route_table_id" ] || {
        echo "failed to resolve DMZ route table id" >&2
        exit 1
      }
      [ -n "$egress_route_table_id" ] || {
        echo "failed to resolve egress route table id" >&2
        exit 1
      }

      route_tables_ready="false"
      for attempt in 1 2 3 4 5 6 7 8 9 10 11 12; do
        route_tables_output="$(HOME="$temp_home" ve transitrouter DescribeTransitRouterRouteTables \
          --profile "$temp_profile" \
          --TransitRouterId "${volcenginecc_transitrouter_transit_router.this.id}" 2>&1)" || {
          printf '%s\n' "$route_tables_output" >&2
          exit 1
        }
        if ROUTE_TABLES_OUTPUT="$route_tables_output" python3 - "$dmz_route_table_id" "$egress_route_table_id" <<'PY'
import json
import os
import sys

targets = {sys.argv[1], sys.argv[2]}
payload = json.loads(os.environ["ROUTE_TABLES_OUTPUT"])
items = payload.get("Result", {}).get("TransitRouterRouteTables")
if items is None:
    items = payload.get("Result", {}).get("RouteTables", [])
seen = set()
for item in items or []:
    route_table_id = (item.get("TransitRouterRouteTableId") or item.get("RouteTableId") or "").strip()
    if route_table_id in targets:
        seen.add(route_table_id)
raise SystemExit(0 if seen == targets else 1)
PY
        then
          route_tables_ready="true"
          break
        fi
        sleep 5
      done
      [ "$route_tables_ready" = "true" ] || {
        echo "transit router route tables did not become visible after waiting" >&2
        printf '%s\n' "$route_tables_output" >&2
        exit 1
      }

      associations_output="$(HOME="$temp_home" ve transitrouter DescribeTransitRouterRouteTableAssociations \
        --profile "$temp_profile" \
        --TransitRouterAttachmentId "${volcenginecc_transitrouter_vpc_attachment.network.transit_router_attachment_id}" \
        --TransitRouterRouteTableId "$dmz_route_table_id" 2>&1)" || {
        printf '%s\n' "$associations_output" >&2
        exit 1
      }
      association_probe="$(ASSOCIATIONS_OUTPUT="$associations_output" python3 - "$dmz_route_table_id" <<'PY'
import json
import os
import sys

target = sys.argv[1]
payload = json.loads(os.environ["ASSOCIATIONS_OUTPUT"])
items = payload.get("Result", {}).get("TransitRouterRouteTableAssociations")
if items is None:
    items = payload.get("Result", {}).get("RouteTableAssociations", [])

for item in items or []:
    route_table_id = (item.get("TransitRouterRouteTableId") or item.get("RouteTableId") or "").strip()
    status = (item.get("Status") or "").upper()
    if route_table_id == target and status in ("AVAILABLE", "ASSOCIATED"):
        print("READY")
        raise SystemExit(0)

for item in items or []:
    route_table_id = (item.get("TransitRouterRouteTableId") or item.get("RouteTableId") or "").strip()
    status = (item.get("Status") or "").upper()
    if route_table_id and status not in ("DISASSOCIATED", "DELETING", "DELETED"):
        print(f"CURRENT:{route_table_id}:{status}")
        raise SystemExit(0)

print("NONE")
PY
      )"
      case "$association_probe" in
        READY)
          ;;
          CURRENT:*|NONE)
          associate_output="$(HOME="$temp_home" ve transitrouter AssociateTransitRouterAttachmentToRouteTable \
            --profile "$temp_profile" \
              --TransitRouterAttachmentId "${volcenginecc_transitrouter_vpc_attachment.network.transit_router_attachment_id}" \
            --TransitRouterRouteTableId "$dmz_route_table_id" 2>&1)" || {
              modify_association_output="$(HOME="$temp_home" ve transitrouter ModifyTransitRouterRouteTableAssociationAttributes \
                --profile "$temp_profile" \
                --TransitRouterAttachmentId "${volcenginecc_transitrouter_vpc_attachment.network.transit_router_attachment_id}" \
                --TransitRouterRouteTableId "$dmz_route_table_id" 2>&1)" || {
                printf '%s\n' "$associate_output" >&2
                printf '%s\n' "$modify_association_output" >&2
                exit 1
              }
            }
          ;;
        *)
          echo "unexpected association probe result: $association_probe" >&2
          exit 1
          ;;
      esac

      association_ready="false"
      for attempt in 1 2 3 4 5 6 7 8 9 10 11 12; do
        associations_output="$(HOME="$temp_home" ve transitrouter DescribeTransitRouterRouteTableAssociations \
          --profile "$temp_profile" \
          --TransitRouterAttachmentId "${volcenginecc_transitrouter_vpc_attachment.network.transit_router_attachment_id}" \
          --TransitRouterRouteTableId "$dmz_route_table_id" 2>&1)" || {
          printf '%s\n' "$associations_output" >&2
          exit 1
        }
        if ASSOCIATIONS_OUTPUT="$associations_output" python3 - "$dmz_route_table_id" <<'PY'
import json
import os
import sys

target = sys.argv[1]
payload = json.loads(os.environ["ASSOCIATIONS_OUTPUT"])
items = payload.get("Result", {}).get("TransitRouterRouteTableAssociations")
if items is None:
    items = payload.get("Result", {}).get("RouteTableAssociations", [])
for item in items or []:
    route_table_id = (item.get("TransitRouterRouteTableId") or item.get("RouteTableId") or "").strip()
    status = (item.get("Status") or "").upper()
    if route_table_id == target and status in ("AVAILABLE", "ASSOCIATED"):
        raise SystemExit(0)
raise SystemExit(1)
PY
        then
          association_ready="true"
          break
        fi
        sleep 5
      done
      [ "$association_ready" = "true" ] || {
        echo "network attachment did not converge to target route table association after waiting" >&2
        printf '%s\n' "$associations_output" >&2
        exit 1
      }

      propagations_output="$(HOME="$temp_home" ve transitrouter DescribeTransitRouterRouteTablePropagations \
        --profile "$temp_profile" \
        --TransitRouterAttachmentId "${volcenginecc_transitrouter_vpc_attachment.network.transit_router_attachment_id}" \
        --TransitRouterRouteTableId "$egress_route_table_id" 2>&1)" || {
        printf '%s\n' "$propagations_output" >&2
        exit 1
      }
      propagation_probe="$(PROPAGATIONS_OUTPUT="$propagations_output" python3 - "$egress_route_table_id" <<'PY'
import json
import os
import sys

target = sys.argv[1]
payload = json.loads(os.environ["PROPAGATIONS_OUTPUT"])
items = payload.get("Result", {}).get("TransitRouterRouteTablePropagations")
if items is None:
    items = payload.get("Result", {}).get("RouteTablePropagations", [])
for item in items or []:
    route_table_id = (item.get("TransitRouterRouteTableId") or item.get("RouteTableId") or "").strip()
    status = (item.get("Status") or "").upper()
    if route_table_id == target and status in ("AVAILABLE", "ASSOCIATED"):
        print("READY")
        raise SystemExit(0)
    if route_table_id == target and status in ("PENDING", "CONFIGURING", "ENABLING"):
        print("IN_PROGRESS")
        raise SystemExit(0)
print("NONE")
PY
      )"
      if [ "$propagation_probe" = "NONE" ]; then
        propagation_output="$(HOME="$temp_home" ve transitrouter EnableTransitRouterRouteTablePropagation \
          --profile "$temp_profile" \
          --TransitRouterAttachmentId "${volcenginecc_transitrouter_vpc_attachment.network.transit_router_attachment_id}" \
          --TransitRouterRouteTableId "$egress_route_table_id" \
          --PropagationGranularity VPC 2>&1)" || {
          printf '%s\n' "$propagation_output" >&2
          exit 1
        }
      fi

      propagation_ready="false"
      for attempt in 1 2 3 4 5 6 7 8 9 10 11 12; do
        propagations_output="$(HOME="$temp_home" ve transitrouter DescribeTransitRouterRouteTablePropagations \
          --profile "$temp_profile" \
          --TransitRouterAttachmentId "${volcenginecc_transitrouter_vpc_attachment.network.transit_router_attachment_id}" \
          --TransitRouterRouteTableId "$egress_route_table_id" 2>&1)" || {
          printf '%s\n' "$propagations_output" >&2
          exit 1
        }
        if PROPAGATIONS_OUTPUT="$propagations_output" python3 - "$egress_route_table_id" <<'PY'
import json
import os
import sys

target = sys.argv[1]
payload = json.loads(os.environ["PROPAGATIONS_OUTPUT"])
items = payload.get("Result", {}).get("TransitRouterRouteTablePropagations")
if items is None:
    items = payload.get("Result", {}).get("RouteTablePropagations", [])
for item in items or []:
    route_table_id = (item.get("TransitRouterRouteTableId") or item.get("RouteTableId") or "").strip()
    status = (item.get("Status") or "").upper()
    if route_table_id == target and status in ("AVAILABLE", "ASSOCIATED"):
        raise SystemExit(0)
raise SystemExit(1)
PY
        then
          propagation_ready="true"
          break
        fi
        sleep 5
      done
      [ "$propagation_ready" = "true" ] || {
        echo "network attachment propagation did not converge after waiting" >&2
        printf '%s\n' "$propagations_output" >&2
        exit 1
      }

      route_entries_output="$(HOME="$temp_home" ve transitrouter DescribeTransitRouterRouteEntries \
        --profile "$temp_profile" \
        --TransitRouterRouteTableId "$egress_route_table_id" \
        --DestinationCidrBlock "0.0.0.0/0" 2>&1)" || {
        printf '%s\n' "$route_entries_output" >&2
        exit 1
      }
      route_entry_probe="$(ROUTE_ENTRIES_OUTPUT="$route_entries_output" python3 - "${volcenginecc_transitrouter_vpc_attachment.network.transit_router_attachment_id}" <<'PY'
import json
import os
import sys

target = sys.argv[1]
payload = json.loads(os.environ["ROUTE_ENTRIES_OUTPUT"])
items = payload.get("Result", {}).get("TransitRouterRouteEntries")
if items is None:
    items = payload.get("Result", {}).get("RouteEntries", [])
for item in items or []:
    destination = (item.get("DestinationCidrBlock") or "").strip()
    hop_id = (item.get("TransitRouterRouteEntryNextHopId") or item.get("NextHopId") or "").strip()
    hop_type = (item.get("TransitRouterRouteEntryNextHopType") or item.get("NextHopType") or "").strip()
    status = (item.get("Status") or "").upper()
    if destination == "0.0.0.0/0" and hop_id == target and hop_type == "Attachment" and status == "AVAILABLE":
        print("READY")
        raise SystemExit(0)
    if destination == "0.0.0.0/0" and hop_id == target and hop_type == "Attachment" and status in ("PENDING", "CONFIGURING", "CREATING"):
        print("IN_PROGRESS")
        raise SystemExit(0)
print("NONE")
PY
      )"
      if [ "$route_entry_probe" = "NONE" ]; then
        create_route_entry_output="$(HOME="$temp_home" ve transitrouter CreateTransitRouterRouteEntry \
          --profile "$temp_profile" \
          --TransitRouterRouteTableId "$egress_route_table_id" \
          --TransitRouterRouteEntryName "Default_Route_To_Public" \
          --Description "Default public route" \
          --DestinationCidrBlock "0.0.0.0/0" \
          --TransitRouterRouteEntryNextHopId "${volcenginecc_transitrouter_vpc_attachment.network.transit_router_attachment_id}" \
          --TransitRouterRouteEntryNextHopType Attachment 2>&1)" || {
          printf '%s\n' "$create_route_entry_output" >&2
          exit 1
        }
      fi

      route_entry_ready="false"
      for attempt in 1 2 3 4 5 6 7 8 9 10 11 12; do
        route_entries_output="$(HOME="$temp_home" ve transitrouter DescribeTransitRouterRouteEntries \
          --profile "$temp_profile" \
          --TransitRouterRouteTableId "$egress_route_table_id" \
          --DestinationCidrBlock "0.0.0.0/0" 2>&1)" || {
          printf '%s\n' "$route_entries_output" >&2
          exit 1
        }
        if ROUTE_ENTRIES_OUTPUT="$route_entries_output" python3 - "${volcenginecc_transitrouter_vpc_attachment.network.transit_router_attachment_id}" <<'PY'
import json
import os
import sys

target = sys.argv[1]
payload = json.loads(os.environ["ROUTE_ENTRIES_OUTPUT"])
items = payload.get("Result", {}).get("TransitRouterRouteEntries")
if items is None:
    items = payload.get("Result", {}).get("RouteEntries", [])
for item in items or []:
    destination = (item.get("DestinationCidrBlock") or "").strip()
    hop_id = (item.get("TransitRouterRouteEntryNextHopId") or item.get("NextHopId") or "").strip()
    hop_type = (item.get("TransitRouterRouteEntryNextHopType") or item.get("NextHopType") or "").strip()
    status = (item.get("Status") or "").upper()
    if destination == "0.0.0.0/0" and hop_id == target and hop_type == "Attachment" and status == "AVAILABLE":
        raise SystemExit(0)
raise SystemExit(1)
PY
        then
          route_entry_ready="true"
          break
        fi
        sleep 5
      done
      [ "$route_entry_ready" = "true" ] || {
        echo "default route entry did not converge after waiting" >&2
        printf '%s\n' "$route_entries_output" >&2
        exit 1
      }

      printf '%s\n' "network transit router route tables ready: $dmz_route_table_id / $egress_route_table_id"
    EOT
  }

  depends_on = [volcenginecc_transitrouter_vpc_attachment.network]
}
