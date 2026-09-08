#!/usr/bin/env bash
# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: MIT
# export_outputs.sh — Run `terraform output -json` and write the result to a
# stable path consumed by `volcengine-deploy` (.volcengine/iac-outputs.json by
# default). Sets file mode 0600 because kubeconfig and DB connection strings
# are sensitive.
#
# Usage:
#   export_outputs.sh                     # writes .volcengine/iac-outputs.json
#   export_outputs.sh --tf-dir ./infra    # cd into a Terraform dir first
#   export_outputs.sh --output /path/out.json

set -uo pipefail

tf_dir="."
output_path=""
while [ $# -gt 0 ]; do
  case "$1" in
    --tf-dir) tf_dir="$2"; shift 2 ;;
    --output) output_path="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if ! command -v terraform >/dev/null 2>&1; then
  echo "Error: terraform CLI not found in PATH" >&2
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is required" >&2
  exit 1
fi

output_path="${output_path:-$tf_dir/.volcengine/iac-outputs.json}"
mkdir -p "$(dirname "$output_path")"

cd "$tf_dir"

# Capture and validate
raw=$(terraform output -json 2>/dev/null) || {
  echo "Error: 'terraform output -json' failed. Did you run 'terraform apply' first?" >&2
  exit 1
}

# Sanity check — non-empty JSON object
echo "$raw" | jq -e 'type == "object"' >/dev/null || {
  echo "Error: terraform output did not return a JSON object" >&2
  exit 1
}

echo "$raw" > "$output_path"
chmod 0600 "$output_path"

# Print a human summary of available keys
keys=$(echo "$raw" | jq -r 'keys[]' | tr '\n' ' ')
echo "Wrote $output_path (mode 0600)"
echo "Available outputs: $keys"
