locals {
  network_account_assume_role_trn  = "trn:iam::${var.network_account_id}:role/OrganizationAccessControlRole"
  transit_router_resource_trn      = "trn:transitrouter:${var.region}:${var.network_account_id}:transitrouter/${var.transit_router_id}"
  resource_share_member_account_id = var.account_id
}

resource "volcenginecc_vpc_vpc" "workload" {
  provider = volcenginecc.member

  cidr_block  = var.workload_vpc_cidr
  vpc_name    = "${var.account_id}-workload-vpc"
  description = "Account Factory workload VPC attached to shared transit router"
}

resource "volcenginecc_vpc_subnet" "workload_az_a" {
  provider = volcenginecc.member

  vpc_id      = volcenginecc_vpc_vpc.workload.id
  zone_id     = var.availability_zone_a
  cidr_block  = var.workload_subnet_cidr_az_a
  subnet_name = "${var.account_id}-workload-subnet-a"
}

resource "volcenginecc_vpc_subnet" "workload_az_b" {
  provider = volcenginecc.member

  vpc_id      = volcenginecc_vpc_vpc.workload.id
  zone_id     = var.availability_zone_b
  cidr_block  = var.workload_subnet_cidr_az_b
  subnet_name = "${var.account_id}-workload-subnet-b"

  depends_on = [volcenginecc_vpc_subnet.workload_az_a]
}

resource "null_resource" "shared_transit_router_member_account_association" {
  count = var.attach_to_shared_network ? 1 : 0

  triggers = {
    account_id                         = var.account_id
    network_account_id                 = var.network_account_id
    region                             = var.region
    transit_router_id                  = var.transit_router_id
    transit_router_resource_share_name = var.transit_router_resource_share_name
    transit_router_resource_trn        = local.transit_router_resource_trn
  }

  provisioner "local-exec" {
    interpreter = ["/bin/sh", "-c"]
    command     = <<-EOT
      set -eu

      assume_role_output="$(ve sts AssumeRole \
        --RoleTrn "${local.network_account_assume_role_trn}" \
        --RoleSessionName "af-network-share")"

      temp_profile="af-network-share-${var.network_account_id}"
      temp_home="$(mktemp -d -t af-network-share-home.XXXXXX)"
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
        --Name "${var.transit_router_resource_share_name}" \
        --ResourceOwner SELF 2>&1)" || {
        printf '%s\n' "$describe_shares_output" >&2
        exit 1
      }

      resource_share_trn="$(DESCRIBE_SHARES_OUTPUT="$describe_shares_output" python3 - "${var.transit_router_resource_share_name}" <<'PY'
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

      [ -n "$resource_share_trn" ] || {
        echo "shared transit router resource share ${var.transit_router_resource_share_name} was not found in network account ${var.network_account_id}; complete 05-network first" >&2
        printf '%s\n' "$describe_shares_output" >&2
        exit 1
      }

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
        echo "shared transit router resource ${local.transit_router_resource_trn} is not ASSOCIATED in resource share $resource_share_trn; complete 05-network first" >&2
        printf '%s\n' "$resource_associations_output" >&2
        exit 1
      }

      associate_principal_output=""
      if associate_principal_output="$(HOME="$temp_home" ve resourceshare AssociateResourceShare \
        --profile "$temp_profile" \
        --ResourceShareTrn "$resource_share_trn" \
        --Principals "${local.resource_share_member_account_id}" 2>&1)"; then
        :
      elif printf '%s' "$associate_principal_output" | grep -Eqi 'DuplicatedAssociation|PrincipalConflict|DuplicatedInvitation|already exist|重复|已存在'; then
        :
      else
        echo "failed to associate member account ${local.resource_share_member_account_id} into resource share $resource_share_trn" >&2
        printf '%s\n' "$associate_principal_output" >&2
        exit 1
      fi

      principal_associated="false"
      for attempt in 1 2 3 4 5 6; do
        principal_associations_output="$(HOME="$temp_home" ve resourceshare ListResourceShareAssociations \
          --profile "$temp_profile" \
          --ResourceShareTrn "$resource_share_trn" \
          --AssociationType PRINCIPAL 2>&1)" || {
          printf '%s\n' "$principal_associations_output" >&2
          exit 1
        }
        if PRINCIPAL_ASSOCIATIONS_OUTPUT="$principal_associations_output" python3 - "${local.resource_share_member_account_id}" <<'PY'
import json
import os
import sys

target = sys.argv[1]
payload = json.loads(os.environ["PRINCIPAL_ASSOCIATIONS_OUTPUT"])
for association in payload.get("Result", {}).get("Associations", []):
    if association.get("AssociationEntity") == target and association.get("Status") == "ASSOCIATED":
        raise SystemExit(0)
raise SystemExit(1)
PY
        then
          principal_associated="true"
          break
        fi
        sleep 5
      done
      [ "$principal_associated" = "true" ] || {
        echo "member account ${local.resource_share_member_account_id} is not ASSOCIATED in resource share $resource_share_trn after waiting" >&2
        printf '%s\n' "$principal_associations_output" >&2
        exit 1
      }

      printf '%s\n' "resource share ready for member account: $resource_share_trn -> ${local.resource_share_member_account_id}"
    EOT
  }

  depends_on = [volcenginecc_vpc_subnet.workload_az_b]
}

# Transit Router 服务关联角色（SLR）。
# volcenginecc provider 无对应资源类型，只能用 `ve iam CreateServiceLinkedRole` CLI 创建（幂等）。
# 注意：local-exec 不会继承 provider 的 assume_role 身份，因此此处需自行 AssumeRole 一次，
# 写临时 profile 并显式 --profile 调用，避免 ve CLI 落回本机默认 profile。
resource "null_resource" "workload_transitrouter_service_linked_role" {
  count = var.attach_to_shared_network ? 1 : 0

  triggers = {
    account_id = var.account_id
    region     = var.region
  }

  provisioner "local-exec" {
    interpreter = ["/bin/sh", "-c"]
    command     = <<-EOT
      set -eu

      assume_role_output="$(ve sts AssumeRole \
        --RoleTrn "trn:iam::${var.account_id}:role/OrganizationAccessControlRole" \
        --RoleSessionName "af-network-slr")"

      temp_profile="af-network-slr-${var.account_id}"
      temp_home="$(mktemp -d -t af-network-slr-home.XXXXXX)"
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
    print("failed to assume member account role: no JSON payload found in AssumeRole response", file=sys.stderr)
    raise SystemExit(1)
payload = json.loads(raw[json_start:])
credentials = payload.get("Result", {}).get("Credentials", {})

if (
    not credentials.get("AccessKeyId")
    or not credentials.get("SecretAccessKey")
    or not credentials.get("SessionToken")
):
    print("failed to assume member account role: credentials not found in AssumeRole response", file=sys.stderr)
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
      printf '%s' "$identity" | grep -q "${var.account_id}" || {
        echo "temporary member slr execution identity probe did not match member account ${var.account_id}" >&2
        printf '%s\n' "$identity" >&2
        exit 1
      }

      # 4. 幂等创建 SLR：已存在视为成功
      create_out="$(HOME="$temp_home" ve iam CreateServiceLinkedRole --profile "$temp_profile" --ServiceName transitrouter 2>&1)" && exit 0
      printf '%s' "$create_out" | grep -Eqi 'RoleAlreadyExists|already exists|重复|已存在' && exit 0
      printf '%s\n' "$create_out" >&2
      exit 1
    EOT
  }

  depends_on = [null_resource.shared_transit_router_member_account_association]
}

resource "volcenginecc_transitrouter_vpc_attachment" "workload" {
  count    = var.attach_to_shared_network ? 1 : 0
  provider = volcenginecc.member

  transit_router_id              = var.transit_router_id
  vpc_id                         = volcenginecc_vpc_vpc.workload.id
  transit_router_attachment_name = "${var.account_id}-workload-attach"
  description                    = "Account Factory workload VPC attachment"
  auto_publish_route_enabled     = true

  attach_points = [
    {
      subnet_id = volcenginecc_vpc_subnet.workload_az_a.id
      zone_id   = var.availability_zone_a
    },
    {
      subnet_id = volcenginecc_vpc_subnet.workload_az_b.id
      zone_id   = var.availability_zone_b
    }
  ]

  depends_on = [null_resource.workload_transitrouter_service_linked_role]
}

resource "null_resource" "shared_transit_router_route_table_binding" {
  count = var.attach_to_shared_network ? 1 : 0

  triggers = {
    account_id                            = var.account_id
    network_account_id                    = var.network_account_id
    region                                = var.region
    transit_router_id                     = var.transit_router_id
    workload_vpc_attachment_id            = volcenginecc_transitrouter_vpc_attachment.workload[0].transit_router_attachment_id
    transit_router_dmz_public_route_table = var.transit_router_dmz_public_route_table_name
    transit_router_egress_route_table     = var.transit_router_egress_route_table_name
  }

  provisioner "local-exec" {
    interpreter = ["/bin/sh", "-c"]
    command     = <<-EOT
      set -eu

      assume_role_output="$(ve sts AssumeRole \
        --RoleTrn "${local.network_account_assume_role_trn}" \
        --RoleSessionName "af-network-tr-route")"

      temp_profile="af-network-tr-route-${var.network_account_id}"
      temp_home="$(mktemp -d -t af-network-tr-route-home.XXXXXX)"
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
        echo "temporary network route table binding identity probe did not match network account ${var.network_account_id}" >&2
        printf '%s\n' "$identity" >&2
        exit 1
      }

      route_tables_output="$(HOME="$temp_home" ve transitrouter DescribeTransitRouterRouteTables \
        --profile "$temp_profile" \
        --TransitRouterId "${var.transit_router_id}" 2>&1)" || {
        printf '%s\n' "$route_tables_output" >&2
        exit 1
      }

      route_table_ids="$(ROUTE_TABLES_OUTPUT="$route_tables_output" python3 - "${var.transit_router_dmz_public_route_table_name}" "${var.transit_router_egress_route_table_name}" <<'PY'
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

      [ -n "$dmz_route_table_id" ] || {
        echo "route table ${var.transit_router_dmz_public_route_table_name} was not found in shared transit router ${var.transit_router_id}; complete or repair 05-network first" >&2
        exit 1
      }
      [ -n "$egress_route_table_id" ] || {
        echo "route table ${var.transit_router_egress_route_table_name} was not found in shared transit router ${var.transit_router_id}; complete or repair 05-network first" >&2
        exit 1
      }

      egress_default_route_ready="false"
      for attempt in 1 2 3 4 5 6 7 8 9 10 11 12; do
        route_entries_output="$(HOME="$temp_home" ve transitrouter DescribeTransitRouterRouteEntries \
          --profile "$temp_profile" \
          --TransitRouterRouteTableId "$egress_route_table_id" \
          --DestinationCidrBlock "0.0.0.0/0" 2>&1)" || {
          printf '%s\n' "$route_entries_output" >&2
          exit 1
        }
        if ROUTE_ENTRIES_OUTPUT="$route_entries_output" python3 - "${var.network_vpc_attachment_id}" <<'PY'
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
          egress_default_route_ready="true"
          break
        fi
        sleep 5
      done
      [ "$egress_default_route_ready" = "true" ] || {
        echo "egress route table ${var.transit_router_egress_route_table_name} does not have an AVAILABLE default route 0.0.0.0/0 -> ${var.network_vpc_attachment_id}; complete or repair 05-network first" >&2
        printf '%s\n' "$route_entries_output" >&2
        exit 1
      }

      associations_output="$(HOME="$temp_home" ve transitrouter DescribeTransitRouterRouteTableAssociations \
        --profile "$temp_profile" \
        --TransitRouterAttachmentId "${volcenginecc_transitrouter_vpc_attachment.workload[0].transit_router_attachment_id}" \
        --TransitRouterRouteTableId "$egress_route_table_id" 2>&1)" || {
        printf '%s\n' "$associations_output" >&2
        exit 1
      }
      association_probe="$(ASSOCIATIONS_OUTPUT="$associations_output" python3 - "$egress_route_table_id" <<'PY'
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
              --TransitRouterAttachmentId "${volcenginecc_transitrouter_vpc_attachment.workload[0].transit_router_attachment_id}" \
            --TransitRouterRouteTableId "$egress_route_table_id" 2>&1)" || {
              modify_association_output="$(HOME="$temp_home" ve transitrouter ModifyTransitRouterRouteTableAssociationAttributes \
                --profile "$temp_profile" \
                --TransitRouterAttachmentId "${volcenginecc_transitrouter_vpc_attachment.workload[0].transit_router_attachment_id}" \
                --TransitRouterRouteTableId "$egress_route_table_id" 2>&1)" || {
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
          --TransitRouterAttachmentId "${volcenginecc_transitrouter_vpc_attachment.workload[0].transit_router_attachment_id}" \
          --TransitRouterRouteTableId "$egress_route_table_id" 2>&1)" || {
          printf '%s\n' "$associations_output" >&2
          exit 1
        }
        if ASSOCIATIONS_OUTPUT="$associations_output" python3 - "$egress_route_table_id" <<'PY'
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
        echo "workload attachment did not converge to target route table association after waiting" >&2
        printf '%s\n' "$associations_output" >&2
        exit 1
      }

      propagations_output="$(HOME="$temp_home" ve transitrouter DescribeTransitRouterRouteTablePropagations \
        --profile "$temp_profile" \
        --TransitRouterAttachmentId "${volcenginecc_transitrouter_vpc_attachment.workload[0].transit_router_attachment_id}" \
        --TransitRouterRouteTableId "$dmz_route_table_id" 2>&1)" || {
        printf '%s\n' "$propagations_output" >&2
        exit 1
      }
      propagation_probe="$(PROPAGATIONS_OUTPUT="$propagations_output" python3 - "$dmz_route_table_id" <<'PY'
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
          --TransitRouterAttachmentId "${volcenginecc_transitrouter_vpc_attachment.workload[0].transit_router_attachment_id}" \
          --TransitRouterRouteTableId "$dmz_route_table_id" \
          --PropagationGranularity VPC 2>&1)" || {
          printf '%s\n' "$propagation_output" >&2
          exit 1
        }
      fi

      propagation_ready="false"
      for attempt in 1 2 3 4 5 6 7 8 9 10 11 12; do
        propagations_output="$(HOME="$temp_home" ve transitrouter DescribeTransitRouterRouteTablePropagations \
          --profile "$temp_profile" \
          --TransitRouterAttachmentId "${volcenginecc_transitrouter_vpc_attachment.workload[0].transit_router_attachment_id}" \
          --TransitRouterRouteTableId "$dmz_route_table_id" 2>&1)" || {
          printf '%s\n' "$propagations_output" >&2
          exit 1
        }
        if PROPAGATIONS_OUTPUT="$propagations_output" python3 - "$dmz_route_table_id" <<'PY'
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
        echo "workload attachment propagation did not converge after waiting" >&2
        printf '%s\n' "$propagations_output" >&2
        exit 1
      }

      printf '%s\n' "shared transit router route table binding ready: ${volcenginecc_transitrouter_vpc_attachment.workload[0].transit_router_attachment_id}"
    EOT
  }

  depends_on = [volcenginecc_transitrouter_vpc_attachment.workload]
}
