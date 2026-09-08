#!/usr/bin/env bash
# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: MIT
# check-region-services.sh — Probe whether ECS / VKE / CR / veFaaS are
# available in the current $VOLCENGINE_REGION using the cheapest read-only API
# per service. Output JSON with four booleans and a list of probe failures.
#
# Strategy: run each probe, capture stdout+stderr, mark service as available
# unless the response carries an explicit "Service*Unavailable", "NotSupport",
# or auth/permission failure. Quota errors are treated as "service exists but
# limited" which still counts as available.

set -uo pipefail

region="${VOLCENGINE_REGION:-}"
if [ -z "$region" ]; then
  echo '{"error": "VOLCENGINE_REGION is not set"}' >&2
  exit 1
fi

if ! command -v ve >/dev/null 2>&1; then
  echo '{"error": "ve CLI not found in PATH"}' >&2
  exit 1
fi

# Run one probe; print "true" or "false" and capture failure reason.
# Args: <service-tag> <command...>
probe() {
  local tag="$1"
  shift
  local out
  out=$("$@" 2>&1) || true

  # Definitive unavailable signals
  if echo "$out" | grep -qiE 'ServiceNotAvailable|NotSupportedRegion|RegionNotSupported|NoSuchService|InvalidEndpoint|Failed to find endpoint'; then
    echo "false|$tag: service not available in region"
    return
  fi

  # Auth/permission failures prove the endpoint exists; record that access was denied.
  if echo "$out" | grep -qiE 'Forbidden|UnauthorizedOperation|AccessDenied|NoPermission'; then
    echo "true|$tag: endpoint responded but access was denied"
    return
  fi

  # Quota errors — service exists, just no headroom
  if echo "$out" | grep -qiE 'QuotaExceeded|LimitExceeded'; then
    echo "true|$tag: quota limited (service available)"
    return
  fi

  # Network or transport errors — inconclusive, default to false
  if echo "$out" | grep -qiE 'connection refused|no such host|timeout'; then
    echo "false|$tag: network error during probe"
    return
  fi

  # Otherwise: presence of "ResponseMetadata" or absence of "Error" implies success
  if echo "$out" | grep -q '"ResponseMetadata"' && ! echo "$out" | grep -q '"Error"'; then
    echo "true|"
    return
  fi

  # Fallback: any other unexpected error → mark unavailable for safety
  local first_err
  first_err=$(echo "$out" | grep -oE '"Code":"[^"]+"' | head -1 | tr -d '"' | sed 's/Code://')
  echo "false|$tag: ${first_err:-unknown probe failure}"
}

# Probe each service. Order: ECS (always present) → CR → VKE → veFaaS.
ecs_result=$(probe "ecs" ve ecs DescribeAvailableResource \
  --ZoneId "${region}-a" --DestinationResource InstanceType)
cr_result=$(probe "cr" ve cr ListRegistries --body '{"PageNumber":1,"PageSize":1}')
vke_result=$(probe "vke" ve vke ListClusters --body '{"PageNumber":1,"PageSize":1}')
faas_result=$(probe "vefaas" ve vefaas ListFunctions --body '{"PageNumber":1,"PageSize":1}')

ecs_ok="${ecs_result%%|*}"
cr_ok="${cr_result%%|*}"
vke_ok="${vke_result%%|*}"
faas_ok="${faas_result%%|*}"

notes=()
for r in "$ecs_result" "$cr_result" "$vke_result" "$faas_result"; do
  msg="${r#*|}"
  [ -n "$msg" ] && notes+=("$msg")
done

# Build notes JSON array
notes_json="["
for i in ${!notes[@]+"${!notes[@]}"}; do
  [ "$i" -gt 0 ] && notes_json+=","
  esc=${notes[$i]//\"/\\\"}
  notes_json+="\"$esc\""
done
notes_json+="]"

cat <<EOF
{
  "region": "$region",
  "ecs_available": $ecs_ok,
  "cr_available": $cr_ok,
  "vke_available": $vke_ok,
  "faas_available": $faas_ok,
  "notes": $notes_json
}
EOF
