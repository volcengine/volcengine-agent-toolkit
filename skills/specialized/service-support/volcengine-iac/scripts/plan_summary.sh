#!/usr/bin/env bash
# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: MIT
# plan_summary.sh — Read a `terraform show -json <plan-file>` from stdin or a
# file argument and emit a readable resource-change summary grouped by action.
#
# Usage:
#   terraform show -json tfplan.binary | plan_summary.sh
#   plan_summary.sh tfplan.json

set -uo pipefail

if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is required" >&2
  exit 1
fi

input="${1:-/dev/stdin}"

if [ "$input" != "/dev/stdin" ] && [ ! -f "$input" ]; then
  echo "Error: file not found: $input" >&2
  exit 1
fi

cleanup_tmp=""
if [ "$input" = "/dev/stdin" ]; then
  cleanup_tmp="$(mktemp)"
  cat >"$cleanup_tmp"
  input="$cleanup_tmp"
fi
trap 'rm -f "$cleanup_tmp"' EXIT

jq -r '
def emoji(act):
  if act == "create" then "+"
  elif act == "update" then "~"
  elif act == "delete" then "-"
  elif act == "replace" then "±"
  elif act == "no-op" then "."
  else "?" end;

# Newer plan format: .resource_changes[] has .change.actions[]
.resource_changes // [] |
  group_by(.change.actions | sort | join(",")) as $groups |
  $groups[] |
  (.[0].change.actions | sort | join("+")) as $act_label |
  "\n=== \($act_label | ascii_upcase) (\(length) resources) ===",
  (.[] | "  \(emoji(.change.actions[0])) \(.address)")
' "$input" || {
  echo "Error: failed to parse plan JSON. Did you run \`terraform show -json\` first?" >&2
  exit 1
}

# Tail summary line
summary=$(jq -r '
  .resource_changes // [] |
  reduce .[] as $c (
    {create:0, update:0, delete:0, replace:0, noop:0};
    if ($c.change.actions | sort) == ["create"] then .create += 1
    elif ($c.change.actions | sort) == ["update"] then .update += 1
    elif ($c.change.actions | sort) == ["delete"] then .delete += 1
    elif ($c.change.actions | sort) == ["create","delete"] then .replace += 1
    elif ($c.change.actions | sort) == ["no-op"] then .noop += 1
    else . end
  ) |
  "\nPlan: \(.create) to add, \(.update) to change, \(.delete) to destroy, \(.replace) to replace, \(.noop) no-op."
' "$input" 2>/dev/null)
[ -n "$summary" ] && echo "$summary"
exit 0
