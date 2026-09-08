#!/usr/bin/env bash
# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: MIT
# gen-systemd-unit.sh — Generate a systemd unit file for a deployed binary.
# Output goes to stdout; redirect to /etc/systemd/system/<name>.service.
#
# Usage:
#   gen-systemd-unit.sh --name <service-name> --exec <ExecStart-cmd> \
#                       [--user appuser] [--workdir /opt/<name>] [--env-file PATH]
#                       [--description "..."]

set -uo pipefail

name=""
exec=""
user_name="appuser"
work_dir=""
env_file=""
desc=""

while [ $# -gt 0 ]; do
  case "$1" in
    --name) name="$2"; shift 2 ;;
    --exec) exec="$2"; shift 2 ;;
    --user) user_name="$2"; shift 2 ;;
    --workdir) work_dir="$2"; shift 2 ;;
    --env-file) env_file="$2"; shift 2 ;;
    --description) desc="$2"; shift 2 ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if [ -z "$name" ] || [ -z "$exec" ]; then
  echo "Error: --name and --exec are required" >&2
  exit 2
fi

[ -z "$work_dir" ] && work_dir="/opt/$name"
[ -z "$desc" ] && desc="$name service (managed by volcengine-deploy)"

cat <<EOF
[Unit]
Description=$desc
After=network.target

[Service]
Type=simple
User=$user_name
Group=$user_name
WorkingDirectory=$work_dir
EOF

if [ -n "$env_file" ]; then
  echo "EnvironmentFile=-$env_file"
fi

cat <<EOF
ExecStart=$exec
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF
