#!/usr/bin/env python3
# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: MIT
"""Fetch Volcengine SDK install/dependency info for an API (on demand).

Returns the per-language install command (`RunCommand`) plus package and version
from the API Explorer `sdk-info` endpoint. The result is service-level: only
`ServiceCode` and `APIVersion` matter; `APIAction` is not required.

Only call this when the user explicitly asks how to install the SDK or which
package/version to use. Do not run it during normal code generation.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://api.volcengine.com/api/common"

# Map user language input to the endpoint's `Language` values.
LANG_ALIASES = {
    "python": "Python",
    "py": "Python",
    "go": "Go",
    "golang": "Go",
    "java": "Java",
    "php": "Php",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
}


def http_get_json(url: str, *, timeout: int = 20) -> dict:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "volcengine-sdk-info-skill/1.0",
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {url}: {body}") from exc


def fetch_sdk_info(service_code: str, api_version: str) -> list[dict]:
    params = urllib.parse.urlencode(
        {"ServiceCode": service_code, "APIVersion": api_version}
    )
    data = http_get_json(f"{API_BASE}/explorer/sdk-info?{params}")
    result = data.get("Result") or {}
    entries = result.get("SdkInfo") or []
    # Keep only entries that actually carry install info (drop Curl / empty).
    return [
        e
        for e in entries
        if isinstance(e, dict) and not e.get("NoSDKInfo") and e.get("RunCommand")
    ]


def normalize_language(language: str | None) -> str | None:
    if not language:
        return None
    return LANG_ALIASES.get(language.strip().lower(), language)


def format_text(entries: list[dict]) -> str:
    blocks = []
    for e in entries:
        lines = [
            f"{e.get('Language')} {e.get('SdkVersion')} "
            f"({e.get('SdkPackageManagePlatform')})"
        ]
        if e.get("SdkPackage"):
            lines.append(f"  package: {e['SdkPackage']}")
        run = (e.get("RunCommand") or "").rstrip("\n")
        indented = "\n".join("  " + ln for ln in run.splitlines())
        lines.append(f"  install:\n{indented}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch Volcengine SDK install/dependency info for an API."
    )
    parser.add_argument("--service-code", required=True)
    parser.add_argument(
        "--api-version", "--version", dest="api_version", required=True
    )
    parser.add_argument(
        "--language",
        help="Filter to one language (e.g. go, python, java, php, nodejs).",
    )
    parser.add_argument("--output", choices=("text", "json"), default="text")
    args = parser.parse_args()

    try:
        all_entries = fetch_sdk_info(args.service_code, args.api_version)
    except Exception as exc:  # surface a clean message to the agent
        print(f"error: {exc}", file=sys.stderr)
        return 1

    entries = all_entries
    selected = normalize_language(args.language)
    if selected:
        entries = [e for e in all_entries if e.get("Language") == selected]
        if not entries:
            avail = ", ".join(e.get("Language") for e in all_entries)
            print(
                f"error: no SDK info for language '{args.language}'. "
                f"Available: {avail}",
                file=sys.stderr,
            )
            return 1

    if args.output == "json":
        print(json.dumps(entries, ensure_ascii=False, indent=2))
    else:
        print(format_text(entries))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
