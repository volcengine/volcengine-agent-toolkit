#!/usr/bin/env bash
# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: MIT
# check_drift.sh — Detect configuration drift with a refresh-only plan.
# This does not write refreshed values into Terraform state. Returns:
#   0 — no drift
#   1 — terraform error (network, auth, or state lock)
#   2 — drift detected; details printed
#
# Output format: human-readable, with a JSON summary at the end for scripting.
#
# Usage:
#   check_drift.sh                  # runs in current dir
#   check_drift.sh --tf-dir ./infra # changes to dir first
#   check_drift.sh --quiet          # only emit JSON summary

set -uo pipefail

tf_dir="."
quiet=false
while [ $# -gt 0 ]; do
  case "$1" in
    --tf-dir) tf_dir="$2"; shift 2 ;;
    --quiet)  quiet=true; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if ! command -v terraform >/dev/null 2>&1; then
  echo "Error: terraform CLI not found" >&2
  exit 1
fi

cd "$tf_dir"

# Pass Volcengine creds to the Terraform s3 backend's required env variable names.
if [ -n "${VOLCENGINE_ACCESS_KEY:-}" ]; then
  export AWS_ACCESS_KEY_ID="$VOLCENGINE_ACCESS_KEY"
fi
if [ -n "${VOLCENGINE_SECRET_KEY:-}" ]; then
  export AWS_SECRET_ACCESS_KEY="$VOLCENGINE_SECRET_KEY"
fi

[ "$quiet" = false ] && echo "→ terraform plan -refresh-only -detailed-exitcode"
plan_out=$(terraform plan -refresh-only -detailed-exitcode -input=false -no-color 2>&1)
ec=$?

case "$ec" in
  0)
    [ "$quiet" = false ] && echo "✅ no drift"
    echo '{"drift":false,"message":"infrastructure matches configuration"}'
    exit 0
    ;;
  2)
    [ "$quiet" = false ] && {
      echo "⚠️  drift detected — these resources have changed outside Terraform:"
      echo "$plan_out" | grep -E '^\s*[~+\-]' | head -50
    }
    changed=$(echo "$plan_out" | grep -cE '^\s*[~+\-] resource')
    echo "{\"drift\":true,\"changed_resources\":$changed,\"message\":\"refresh-only plan is non-empty; run terraform plan to inspect\"}"
    exit 2
    ;;
  *)
    [ "$quiet" = false ] && {
      echo "❌ terraform plan failed (exit $ec):"
      echo "$plan_out" | tail -20
    }
    echo "{\"drift\":\"error\",\"exit_code\":$ec,\"message\":\"terraform plan returned non-standard exit\"}" >&2
    exit 1
    ;;
esac
