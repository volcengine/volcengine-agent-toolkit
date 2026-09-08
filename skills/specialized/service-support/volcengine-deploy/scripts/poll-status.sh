#!/usr/bin/env bash
# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: MIT
# poll-status.sh — Run a probe command on an interval until its stdout
# matches a success pattern, or until max attempts is reached.
#
# Usage:
#   poll-status.sh --cmd "<command>" --pattern "<regex>" \
#                  [--interval 10] [--max-attempts 30] [--quiet]
#
# Exit:
#   0 — pattern matched within budget
#   1 — exhausted attempts without a match
#   2 — invalid arguments

set -uo pipefail

cmd=""
pattern=""
interval=10
max_attempts=30
quiet=false

while [ $# -gt 0 ]; do
  case "$1" in
    --cmd) cmd="$2"; shift 2 ;;
    --pattern) pattern="$2"; shift 2 ;;
    --interval) interval="$2"; shift 2 ;;
    --max-attempts) max_attempts="$2"; shift 2 ;;
    --quiet) quiet=true; shift ;;
    *)
      echo "Unknown arg: $1" >&2
      echo "Usage: $0 --cmd <command> --pattern <regex> [--interval N] [--max-attempts N] [--quiet]" >&2
      exit 2
      ;;
  esac
done

if [ -z "$cmd" ] || [ -z "$pattern" ]; then
  echo "Error: --cmd and --pattern are required" >&2
  exit 2
fi

attempt=0
while [ "$attempt" -lt "$max_attempts" ]; do
  attempt=$((attempt + 1))
  out=$(eval "$cmd" 2>&1 || true)
  if echo "$out" | grep -qE "$pattern"; then
    [ "$quiet" = false ] && echo "[poll-status] match on attempt $attempt"
    exit 0
  fi
  [ "$quiet" = false ] && echo "[poll-status] attempt $attempt/$max_attempts — no match, sleeping ${interval}s"
  sleep "$interval"
done

[ "$quiet" = false ] && echo "[poll-status] exhausted $max_attempts attempts" >&2
exit 1
