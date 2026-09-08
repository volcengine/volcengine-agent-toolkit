#!/usr/bin/env python3
# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: MIT
"""Search Volcengine services and APIs through API Explorer."""

from __future__ import annotations

import argparse
import concurrent.futures
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


API_BASE = "https://api.volcengine.com/api/common"
API_VERSION_PATTERN = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")


def http_json(url: str, *, timeout: int = 10) -> dict[str, Any]:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "x-language": "zh",
        "User-Agent": "volcengine-make-code-skill/rg-rank",
    }
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {url}: {body}") from exc


def clean_highlight(value: Any) -> str:
    text = re.sub(r"</?em>", "", str(value or ""), flags=re.IGNORECASE)
    return html.unescape(text).strip()


def highlight_values(item: dict[str, Any], field: str) -> list[str]:
    values: list[str] = []
    for highlight in item.get("Highlight") or []:
        if not isinstance(highlight, dict) or highlight.get("Field") != field:
            continue
        value = clean_highlight(highlight.get("Summary"))
        if value:
            values.append(value)
    return values


def search_channel(query: str, *, channel: str, limit: int) -> dict[str, Any]:
    params = urllib.parse.urlencode(
        {
            "Query": query,
            "Channel": channel,
            "Limit": max(limit, 1),
            "Offset": 0,
        }
    )
    return http_json(f"{API_BASE}/search/all?{params}")


def parse_service_results(data: dict[str, Any]) -> list[dict[str, Any]]:
    services: list[dict[str, Any]] = []
    items = data.get("Result", {}).get("List", [])
    for rank, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        titles = highlight_values(item, "title")
        abstracts = highlight_values(item, "abstract")
        service_code = abstracts[0] if abstracts else ""
        if not service_code:
            for url in highlight_values(item, "doc_url"):
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                values = query.get("serviceCode") or query.get("ServiceCode") or []
                if values:
                    service_code = values[0]
                    break
        if not service_code:
            continue
        services.append(
            {
                "service_code": service_code,
                "name": titles[0] if titles else "",
                "remote_rank": rank,
            }
        )
    return services


def parse_api_results(data: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    items = data.get("Result", {}).get("List", [])
    for rank, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        biz = item.get("BizInfo") or {}
        service_code = biz.get("ServiceCode")
        version = biz.get("Version")
        action = biz.get("Action")
        if not service_code or not version or not action:
            continue
        abstracts = highlight_values(item, "abstract")
        titles = highlight_values(item, "title")
        content = highlight_values(item, "content")
        name_cn = abstracts[0] if abstracts else (titles[0] if titles else str(action))
        record = {
            "service_code": service_code,
            "api_version": version,
            "action": action,
            "name_cn": name_cn,
            "description": " ".join(dict.fromkeys(abstracts + content)),
            "service_name": biz.get("ServiceCn", ""),
            "is_recommended": bool(biz.get("IsRecommended")),
            "source": "remote_search",
        }
        results.append(
            {
                "source": "remote_search",
                "remote_rank": rank,
                "record": record,
            }
        )
    return results


def prioritize_recommended_versions(
    results: list[dict[str, Any]],
    *,
    query: str,
) -> list[dict[str, Any]]:
    if API_VERSION_PATTERN.search(query):
        return results

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in results:
        record = item.get("record") or {}
        key = (
            str(record.get("service_code", "")).lower(),
            str(record.get("action", "")).lower(),
        )
        grouped.setdefault(key, []).append(item)

    for items in grouped.values():
        if len(items) < 2:
            continue
        items.sort(
            key=lambda item: (
                not bool((item.get("record") or {}).get("is_recommended")),
                int(item.get("remote_rank") or 10**9),
            )
        )

    offsets: dict[tuple[str, str], int] = {}
    prioritized: list[dict[str, Any]] = []
    for item in results:
        record = item.get("record") or {}
        key = (
            str(record.get("service_code", "")).lower(),
            str(record.get("action", "")).lower(),
        )
        offset = offsets.get(key, 0)
        prioritized.append(grouped[key][offset])
        offsets[key] = offset + 1
    return prioritized


def discover_remote(query: str, *, limit: int) -> dict[str, Any]:
    errors: list[str] = []
    services: list[dict[str, Any]] = []
    api_results: list[dict[str, Any]] = []

    api_search_limit = max(limit, 20)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        service_future = executor.submit(
            search_channel,
            query,
            channel="service",
            limit=limit,
        )
        api_future = executor.submit(
            search_channel,
            query,
            channel="api",
            limit=api_search_limit,
        )
        try:
            services = parse_service_results(service_future.result())
        except Exception as exc:
            errors.append(f"service search failed: {exc}")
        try:
            api_results = prioritize_recommended_versions(
                parse_api_results(api_future.result()),
                query=query,
            )
        except Exception as exc:
            errors.append(f"api search failed: {exc}")

    return {
        "source": "remote_search",
        "service_results": services,
        "errors": errors,
        "results": api_results[: max(limit, 0)],
    }


def remote_search(query: str, *, limit: int) -> list[dict[str, Any]]:
    return discover_remote(query, limit=limit)["results"]


def print_output(
    result: dict[str, Any],
    *,
    output_format: str,
) -> None:
    if output_format == "jsonl":
        for item in result["results"]:
            print(json.dumps(item, ensure_ascii=False))
        return
    if output_format == "text":
        for index, item in enumerate(result["results"], start=1):
            record = item["record"]
            recommended = " [recommended]" if record.get("is_recommended") else ""
            print(
                f"{index}. [remote_search]{recommended} remote_rank={item['remote_rank']} "
                f"{record.get('name_cn', '')} | {record.get('service_code')} "
                f"{record.get('api_version')} {record.get('action')}"
            )
        for error in result["errors"]:
            print(f"warning: {error}", file=sys.stderr)
        return
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Search Volcengine services and APIs online.")
    parser.add_argument("--query", required=True, help="Original user query.")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--format", choices=("json", "jsonl", "text"), default="json")
    args = parser.parse_args()

    if not args.query.strip():
        message = "provide a non-empty --query"
        if args.format == "text":
            print(f"error: empty_query: {message}")
        else:
            print(json.dumps({"error": "empty_query", "message": message}, ensure_ascii=False))
        return 2

    result = discover_remote(args.query, limit=args.limit)
    print_output(result, output_format=args.format)
    if not result["results"] and result["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"error": "exception", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
