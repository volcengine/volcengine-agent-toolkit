terraform {
  required_providers {
    volcenginecc = {
      source  = "volcengine/volcenginecc"
      version = "0.0.69"
    }
  }
}

locals {
  landing_zone_context = var.landing_zone_context_path == null ? null : try(
    jsondecode(file(var.landing_zone_context_path)),
    null,
  )
  effective_management_account_id = var.landing_zone_context_path != null ? try(
    local.landing_zone_context.execution_scope.management_account_id == null ? "" : trimspace(tostring(local.landing_zone_context.execution_scope.management_account_id)),
    "",
  ) : (var.management_account_id == null ? "" : trimspace(var.management_account_id))
  effective_network_account_id = var.landing_zone_context_path != null ? try(
    local.landing_zone_context.phase_inputs.network.account_id == null ? "" : trimspace(tostring(local.landing_zone_context.phase_inputs.network.account_id)),
    "",
  ) : (var.network_account_id == null ? "" : trimspace(var.network_account_id))
  confirmed_architecture_path = var.landing_zone_context_path == null ? null : "${dirname(var.landing_zone_context_path)}/confirmed-architecture.json"
  architecture_hash_matches = var.landing_zone_context_path == null ? true : try(
    filesha256(local.confirmed_architecture_path) == local.landing_zone_context.configuration.architecture_sha256,
    false,
  )
  network_account_assume_role_trn    = "trn:iam::${local.effective_network_account_id}:role/OrganizationAccessControlRole"
  resource_share_service_principal   = "resource_share"
  transit_router_resource_share_name = "${var.prefix}-shared-tr-${var.region}"
  transit_router_resource_trn        = "trn:transitrouter:${var.region}:${local.effective_network_account_id}:transitrouter/${volcenginecc_transitrouter_transit_router.this.id}"
  network_availability_zone_a        = coalesce(var.network_availability_zone_a, "${var.region}-a")
  network_availability_zone_b        = coalesce(var.network_availability_zone_b, "${var.region}-b")
  nat_gateway_name                   = coalesce(var.nat_gateway_name, "${var.prefix}-nat")
  nat_eip_name                       = coalesce(var.eip_name, "${var.prefix}-nat-eip")
  nat_snat_entry_name                = coalesce(var.snat_entry_name, "${var.prefix}-default-snat")
  tr_route_table_dmz_public_name     = "RT_DMZ_Public"
  tr_route_table_egress_name         = "RT_Egress_To_Internal"
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
    error_message = "The network phase prefix/region must match the confirmed Landing Zone context."
  }

  assert {
    condition     = local.architecture_hash_matches
    error_message = "confirmed-architecture.json does not match the architecture digest recorded in landing-zone-context.json."
  }

  assert {
    condition     = var.landing_zone_context_path == null ? true : try(local.landing_zone_context.phase_inputs.network.enabled, false)
    error_message = "The network capability is disabled in the confirmed Landing Zone design; skip Phase 05."
  }

  assert {
    condition     = local.effective_management_account_id != ""
    error_message = "A verified management account ID is required."
  }

  assert {
    condition     = local.effective_network_account_id != ""
    error_message = "The network capability requires a non-empty network account binding."
  }
}

check "legacy_network_input_compatibility" {
  assert {
    condition = (
      var.landing_zone_context_path == null ||
      var.management_account_id == null ||
      trimspace(var.management_account_id) == local.effective_management_account_id
    )
    error_message = "management_account_id conflicts with the authoritative Landing Zone context."
  }

  assert {
    condition = (
      var.landing_zone_context_path == null ||
      var.network_account_id == null ||
      trimspace(var.network_account_id) == local.effective_network_account_id
    )
    error_message = "network_account_id conflicts with the authoritative Landing Zone context."
  }
}

# --- Provider: 主账号 (默认) ---
provider "volcenginecc" {
  region = var.region
}

# --- Provider: 网络账号 (通过 assume_role 跨账号) ---
provider "volcenginecc" {
  alias  = "network_account"
  region = var.region

  assume_role = {
    assume_role_trn          = local.network_account_assume_role_trn
    assume_role_session_name = "lz-network-setup"
    duration_seconds         = 3600
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

      printf '%s' "$caller_identity_output" | grep -q "${local.effective_management_account_id}" || {
        echo "current ve login identity did not match expected management account ${local.effective_management_account_id}" >&2
        printf '%s\n' "$caller_identity_output" >&2
        exit 1
      }

      printf '%s\n' "$caller_identity_output"
    EOT
  }

  triggers = {
    management_account_id = local.effective_management_account_id
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
{"AccountId":"${local.effective_network_account_id}","ServicePrincipal":"${local.resource_share_service_principal}"}
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
    network_account_id        = local.effective_network_account_id
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
    network_account_id        = local.effective_network_account_id
    trusted_service_principal = local.resource_share_service_principal
  }

  depends_on = [null_resource.resource_share_trusted_service_delegated_administrator]
}

# ---------------------------------------------------------------
# Part 1.7: 在网络账号中创建可复用的 TR 共享单元
# 说明：
# - 从 volcenginecc 0.0.69 起，ResourceShare 已是原生资源，直接以网络账号 provider 创建并关联 TR 资源。
# - 跨账号身份由 volcenginecc.network_account 的 provider assume_role 承担，无需再显式 AssumeRole + 临时 profile。
# - allow_share_type = "ORG" 保持仅在组织内共享；05-network 只创建共享单元并关联 TR 资源，成员账号范围由账号工厂基线后续逐个追加（principals 留空）。
# ---------------------------------------------------------------
resource "volcenginecc_resourceshare_resource_share" "transit_router" {
  provider = volcenginecc.network_account

  resource_share_name = local.transit_router_resource_share_name
  allow_share_type    = "ORG"
  resource_trns       = local.transit_router_resource_trn

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
# - 通过 volcenginecc_iam_role 在 network_account provider 上创建，跨账号身份由 provider assume_role 承担。
# ---------------------------------------------------------------
resource "volcenginecc_iam_role" "network_account_natgateway_service_linked_role" {
  count    = var.create_nat ? 1 : 0
  provider = volcenginecc.network_account

  role_name              = "ServiceRoleForNatGateway"
  is_service_linked_role = 1
  service_name           = "natgateway"

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
    volcenginecc_iam_role.network_account_natgateway_service_linked_role,
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
# - 通过 volcenginecc_iam_role 在 network_account provider 上创建，跨账号身份由 provider assume_role 承担。
# ---------------------------------------------------------------
resource "volcenginecc_iam_role" "network_account_transitrouter_service_linked_role" {
  provider = volcenginecc.network_account

  role_name              = "ServiceRoleForTransitRouter"
  is_service_linked_role = 1
  service_name           = "transitrouter"

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

  depends_on = [volcenginecc_iam_role.network_account_transitrouter_service_linked_role]
}

# ---------------------------------------------------------------
# Part 4: 预创建中心 TR 的共享路由表骨架
# 说明：
# - 中心 TR 的共享路由策略由网络底座持有，避免后续每个账号基线 run 去争抢共享路由表本体。
# - 网络底座 attachment 视为统一公网出口 / DMZ 方向的下一跳。
# ---------------------------------------------------------------
resource "volcenginecc_transitrouter_transit_router_route_table" "dmz_public" {
  provider = volcenginecc.network_account

  transit_router_id               = volcenginecc_transitrouter_transit_router.this.id
  transit_router_route_table_name = local.tr_route_table_dmz_public_name
  description                     = "DMZ public route table"

  depends_on = [volcenginecc_transitrouter_vpc_attachment.network]
}

resource "volcenginecc_transitrouter_transit_router_route_table" "egress" {
  provider = volcenginecc.network_account

  transit_router_id               = volcenginecc_transitrouter_transit_router.this.id
  transit_router_route_table_name = local.tr_route_table_egress_name
  description                     = "Internal egress route table"

  depends_on = [volcenginecc_transitrouter_vpc_attachment.network]
}

resource "volcenginecc_transitrouter_transit_router_route_table_association" "network_to_dmz_public" {
  provider = volcenginecc.network_account

  transit_router_attachment_id  = volcenginecc_transitrouter_vpc_attachment.network.transit_router_attachment_id
  transit_router_route_table_id = volcenginecc_transitrouter_transit_router_route_table.dmz_public.transit_router_route_table_id
}

resource "volcenginecc_transitrouter_route_table_propagation" "network_to_egress" {
  provider = volcenginecc.network_account

  transit_router_attachment_id  = volcenginecc_transitrouter_vpc_attachment.network.transit_router_attachment_id
  transit_router_route_table_id = volcenginecc_transitrouter_transit_router_route_table.egress.transit_router_route_table_id
}

resource "volcenginecc_transitrouter_transit_router_route_entry" "egress_default_public" {
  provider = volcenginecc.network_account

  transit_router_route_table_id            = volcenginecc_transitrouter_transit_router_route_table.egress.transit_router_route_table_id
  transit_router_route_entry_name          = "Default_Route_To_Public"
  description                              = "Default public route"
  destination_cidr_block                   = "0.0.0.0/0"
  transit_router_route_entry_next_hop_id   = volcenginecc_transitrouter_vpc_attachment.network.transit_router_attachment_id
  transit_router_route_entry_next_hop_type = "Attachment"

  depends_on = [volcenginecc_transitrouter_route_table_propagation.network_to_egress]
}
