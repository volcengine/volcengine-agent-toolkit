#!/usr/bin/env python3
# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: MIT
"""Fetch Volcengine API swagger and call API Explorer make-code."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


API_BASE = "https://api.volcengine.com/api/common"
METHODS = ("get", "post", "put", "delete", "patch", "head", "trace")
LANG_ALIASES = {
    "python": "PYTHON",
    "py": "PYTHON",
    "go": "GO",
    "golang": "GO",
    "java": "JAVA",
    "php": "PHP",
    "curl": "CURL",
    "shell": "CURL",
    "node": "NODEJS",
    "nodejs": "NODEJS",
    "node.js": "NODEJS",
}


def cache_dir() -> Path:
    custom = os.environ.get("VOLCENGINE_MAKE_CODE_CACHE_DIR")
    if custom:
        return Path(custom).expanduser()
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "volcengine-make-code"
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg) / "volcengine-make-code"
    return Path.home() / ".cache" / "volcengine-make-code"


def build_direct_record(
    *,
    service_code: str,
    api_version: str,
    action: str,
) -> dict[str, str]:
    return {
        "service_code": service_code,
        "api_version": api_version,
        "action": action,
        "name_cn": "",
    }


def swagger_info(swagger: dict[str, Any]) -> dict[str, Any]:
    info = swagger.get("info")
    return info if isinstance(info, dict) else {}


def http_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    x_language: str = "zh",
    timeout: int = 20,
) -> dict[str, Any]:
    data = None
    headers = {
        "Accept": "application/json, text/plain, */*",
        "x-language": x_language,
        "User-Agent": "volcengine-make-code-skill/1.0",
    }
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {url}: {body}") from exc


def choose_operation(swagger: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    paths = swagger.get("paths") or {}
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method in METHODS:
            operation = path_item.get(method)
            if isinstance(operation, dict):
                return path, method, operation
    raise ValueError("swagger has no supported operation")


def resolve_ref(swagger: dict[str, Any], value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    ref = value.get("$ref")
    if not ref or not isinstance(ref, str) or not ref.startswith("#/"):
        return value
    current: Any = swagger
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict):
            return value
        current = current.get(part)
    return current if isinstance(current, dict) else value


def first_request_body_schema(swagger: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    request_body = resolve_ref(swagger, operation.get("requestBody"))
    content = request_body.get("content") or {}
    if not isinstance(content, dict) or not content:
        return {}
    preferred = ["application/json", "application/x-www-form-urlencoded", "multipart/form-data"]
    for content_type in [*preferred, *content.keys()]:
        media = content.get(content_type)
        if isinstance(media, dict):
            return resolve_ref(swagger, media.get("schema"))
    return {}


def schema_properties(swagger: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    schema = resolve_ref(swagger, schema)
    props = schema.get("properties")
    if isinstance(props, dict):
        return props
    return {}


def extract_swagger_param_info(swagger: dict[str, Any]) -> dict[str, Any]:
    path, _method, operation = choose_operation(swagger)
    path_item = swagger.get("paths", {}).get(path, {})
    known: set[str] = set()
    required: set[str] = set()
    schemas: dict[str, dict[str, Any]] = {}

    parameters = []
    if isinstance(path_item.get("parameters"), list):
        parameters.extend(path_item["parameters"])
    if isinstance(operation.get("parameters"), list):
        parameters.extend(operation["parameters"])
    for param_ref in parameters:
        param = resolve_ref(swagger, param_ref)
        name = param.get("name")
        if not name:
            continue
        known.add(name)
        schemas[name] = resolve_ref(swagger, param.get("schema")) or {"type": "string"}
        if param.get("required") is True:
            required.add(name)

    body_schema = first_request_body_schema(swagger, operation)
    for name, prop_schema in schema_properties(swagger, body_schema).items():
        known.add(name)
        schemas[name] = resolve_ref(swagger, prop_schema) or {}
    for name in body_schema.get("required") or []:
        if isinstance(name, str):
            required.add(name)

    servers = swagger.get("servers") or []
    region = None
    if servers and isinstance(servers[0], dict):
        variables = servers[0].get("variables") or {}
        for name, variable in variables.items():
            if not isinstance(variable, dict):
                continue
            if variable.get("x-service-region"):
                region = variable.get("default")

    return {
        "known_params": sorted(known),
        "required_params": sorted(required),
        "param_schemas": schemas,
        "default_region": region,
        "_swagger": swagger,
    }


def schema_type(schema: dict[str, Any]) -> str:
    raw_type = schema.get("type")
    if isinstance(raw_type, list):
        raw_type = raw_type[0] if raw_type else ""
    if isinstance(raw_type, str):
        return raw_type
    if isinstance(schema.get("properties"), dict):
        return "object"
    if isinstance(schema.get("items"), dict):
        return "array"
    return ""


def mock_required_object(swagger: dict[str, Any] | None, schema: dict[str, Any], depth: int) -> dict[str, Any]:
    if depth >= 5:
        return {}
    props = schema.get("properties")
    if not isinstance(props, dict):
        return {}
    result: dict[str, Any] = {}
    for child_name in schema.get("required") or []:
        if not isinstance(child_name, str):
            continue
        child_schema = props.get(child_name, {})
        result[child_name] = mock_value_for_schema(
            child_name,
            child_schema if isinstance(child_schema, dict) else {},
            swagger=swagger,
            depth=depth + 1,
        )
    return result


def mock_value_for_schema(
    name: str,
    schema: dict[str, Any],
    *,
    swagger: dict[str, Any] | None = None,
    depth: int = 0,
) -> Any:
    if swagger:
        schema = resolve_ref(swagger, schema)
    lower_name = name.lower()
    value = schema.get("example")
    if value not in (None, "") and is_usable_example(name, value, schema):
        return value

    examples = schema.get("examples")
    if isinstance(examples, list):
        for value in examples:
            if value not in (None, "") and is_usable_example(name, value, schema):
                return value
    elif isinstance(examples, dict):
        for item in examples.values():
            value = item.get("value") if isinstance(item, dict) else item
            if value not in (None, "") and is_usable_example(name, value, schema):
                return value

    value = schema.get("default")
    if value not in (None, "") and is_usable_example(name, value, schema):
        return value

    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and enum_values:
        return enum_values[0]

    current_type = schema_type(schema)
    if current_type == "object":
        return mock_required_object(swagger, schema, depth)
    if current_type == "array":
        item_schema = schema.get("items")
        if not isinstance(item_schema, dict):
            return []
        return [
            mock_value_for_schema(
                name,
                item_schema,
                swagger=swagger,
                depth=depth + 1,
            )
        ]

    if lower_name in {"cidrblock", "cidr", "ipcidr"} or "cidrblock" in lower_name:
        return "172.16.0.0/16"
    if lower_name.endswith("zoneid"):
        return "cn-beijing-a"
    if lower_name.endswith("imageid"):
        return "image-xxxxxxxx"
    if lower_name.endswith("instancetypeid"):
        return "ecs.g1.large"
    if lower_name.endswith("vpcid"):
        return "vpc-xxxxxxxx"
    if lower_name.endswith("subnetid"):
        return "subnet-xxxxxxxx"
    if lower_name.endswith("securitygroupid"):
        return "sg-xxxxxxxx"
    if lower_name.endswith("name"):
        return f"demo-{re.sub(r'[^a-zA-Z0-9]+', '-', name).strip('-').lower() or 'name'}"

    if current_type == "integer":
        return 1
    if current_type == "number":
        return 1.0
    if current_type == "boolean":
        return True
    return f"mock-{re.sub(r'[^a-zA-Z0-9]+', '-', name).strip('-').lower() or 'value'}"


def is_masked_example(value: Any) -> bool:
    if isinstance(value, str):
        return bool(re.search(r"(\*{2,}|X{2,}|x{2,})", value))
    if isinstance(value, list):
        return any(is_masked_example(item) for item in value)
    if isinstance(value, dict):
        return any(is_masked_example(item) for item in value.values())
    return False


def is_usable_example(name: str, value: Any, schema: dict[str, Any]) -> bool:
    if is_masked_example(value):
        return False
    if is_url_style_json_example(value):
        return False
    current_type = schema_type(schema)
    if current_type == "integer":
        if isinstance(value, bool):
            return False
        if isinstance(value, int):
            return True
        if isinstance(value, str):
            try:
                int(value.strip())
                return True
            except (TypeError, ValueError):
                return False
        return False
    if current_type == "number":
        if isinstance(value, bool):
            return False
        if isinstance(value, (int, float)):
            return True
        if isinstance(value, str):
            try:
                float(value.strip())
                return True
            except (TypeError, ValueError):
                return False
        return False
    if current_type == "boolean":
        if isinstance(value, bool):
            return True
        if isinstance(value, str):
            return value.strip().lower() in {"true", "false", "1", "0"}
        return False
    return True


def is_url_style_json_example(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if re.search(r"\b[A-Za-z][A-Za-z0-9_]*\.\d+\.[A-Za-z0-9_]+\s*=", value):
        return True
    if "&" in value and re.search(r"(^|&)[^&=\s]+=[^&]*", value):
        return True
    return False


def apply_missing_required_mocks(
    params: dict[str, Any],
    param_info: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    result = dict(params)
    mocked: dict[str, Any] = {}
    schemas = param_info.get("param_schemas") or {}
    swagger = param_info.get("_swagger") if isinstance(param_info.get("_swagger"), dict) else None
    for name in param_info["required_params"]:
        if name in result:
            continue
        value = mock_value_for_schema(name, schemas.get(name, {}), swagger=swagger)
        result[name] = value
        mocked[name] = value
    return result, mocked


def swagger_cache_path(record: dict[str, Any]) -> Path:
    return (
        cache_dir()
        / "swagger"
        / record["service_code"]
        / record["api_version"]
        / f"{record['action']}.json"
    )


def fetch_swagger(
    record: dict[str, Any],
    *,
    x_language: str,
    refresh: bool = False,
    ttl_seconds: int = 86400,
) -> dict[str, Any]:
    path = swagger_cache_path(record)
    if not refresh and path.exists():
        if time.time() - path.stat().st_mtime < ttl_seconds:
            return json.loads(path.read_text(encoding="utf-8"))

    params = urllib.parse.urlencode(
        {
            "ServiceCode": record["service_code"],
            "Version": record["api_version"],
            "APIVersion": record["api_version"],
            "ActionName": record["action"],
        }
    )
    data = http_json(f"{API_BASE}/explorer/api-swagger?{params}", x_language=x_language)
    candidates = []
    result = data.get("Result")
    if isinstance(result, dict):
        candidates.append(result.get("Api"))
    candidates.append(data.get("Api"))
    swagger = next(
        (
            item
            for item in candidates
            if isinstance(item, dict) and isinstance(item.get("paths"), dict)
        ),
        None,
    )
    if swagger is None:
        raise RuntimeError("api-swagger response did not include swagger object")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(swagger, ensure_ascii=False), encoding="utf-8")
    return swagger


def load_params(args: argparse.Namespace) -> dict[str, Any]:
    if args.params_json and args.params_file:
        raise ValueError("use only one of --params-json or --params-file")
    if args.params_file:
        text = Path(args.params_file).read_text(encoding="utf-8")
    elif args.params_json:
        text = args.params_json
    else:
        return {}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("params must be a JSON object")
    return data


def normalize_language(language: str | None) -> str | None:
    if not language:
        return None
    return LANG_ALIASES.get(language.lower(), language.upper())


def make_payload(
    record: dict[str, Any],
    swagger: dict[str, Any],
    params: dict[str, Any],
    region: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    info = swagger_info(swagger)
    param_info = extract_swagger_param_info(swagger)
    resolved_region = region or param_info.get("default_region") or "cn-beijing"
    payload = {
        "ApiAction": info.get("x-action") or record["action"],
        "ServiceCode": info.get("x-service-code") or record["service_code"],
        "APIVersion": info.get("version") or record["api_version"],
        "Region": resolved_region,
        "Params": params,
    }
    return payload, param_info


def call_make_code(payload: dict[str, Any], *, x_language: str) -> dict[str, Any]:
    return http_json(
        f"{API_BASE}/explorer/make-code",
        method="POST",
        payload=payload,
        x_language=x_language,
    )


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def print_text(output: dict[str, Any]) -> None:
    api = output.get("api") or {}
    print(
        f"{api.get('service_code')} {api.get('api_version')} {api.get('action')} "
        f"{api.get('name_cn', '')}".strip()
    )
    warnings = output.get("warnings") or {}
    mock_notice_value = warnings.get("mock_notice")
    if mock_notice_value:
        print(mock_notice_value)
    selected_code = output.get("code")
    if isinstance(selected_code, str):
        print(selected_code)
        return
    demo_sdk = output.get("raw_demo_sdk") or {}
    for language, code in demo_sdk.items():
        print(f"\n## {language}")
        if isinstance(code, str):
            print(code)
        else:
            print(json.dumps(code, ensure_ascii=False, indent=2))


def ensure_go_fmt_import(code: str) -> str:
    if '"fmt"' in code:
        return code
    lines = code.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        if line.strip() == "import (":
            lines.insert(idx + 1, '\t"fmt"\n')
            return "".join(lines)
    for idx, line in enumerate(lines):
        if line.startswith("import ") and '"fmt"' not in line:
            existing = line[len("import ") :].strip()
            lines[idx] = "import (\n"
            lines.insert(idx + 1, f"\t{existing}\n")
            lines.insert(idx + 2, '\t"fmt"\n')
            lines.insert(idx + 3, ")\n")
            return "".join(lines)
    return code


def add_python_response_print(code: str) -> str:
    if re.search(r"^\s*print\(resp\)", code, re.MULTILINE):
        return code
    pattern = re.compile(r"^(\s*)(api_instance\.[A-Za-z_][A-Za-z0-9_]*\([^#\n]*\))(\s*)$", re.MULTILINE)

    def repl(match: re.Match[str]) -> str:
        indent = match.group(1)
        call = match.group(2)
        suffix = match.group(3)
        return f"{indent}resp = {call}{suffix}\n{indent}print(resp)"

    return pattern.sub(repl, code, count=1)


def add_go_response_print(code: str) -> str:
    if "fmt.Println(resp)" in code:
        return code
    pattern = re.compile(r"^(\s*)_, err = (svc\.[A-Za-z_][A-Za-z0-9_]*\([^#\n]*\))(\s*)$", re.MULTILINE)

    call_indent = ""

    def repl(match: re.Match[str]) -> str:
        nonlocal call_indent
        call_indent = match.group(1)
        return f"{match.group(1)}resp, err := {match.group(2)}{match.group(3)}"

    code, count = pattern.subn(repl, code, count=1)
    if not count:
        return code
    code = ensure_go_fmt_import(code)
    api_call = re.search(
        rf"(?m)^{re.escape(call_indent)}resp, err := svc\.[A-Za-z_][A-Za-z0-9_]*\([^#\n]*\)\s*$",
        code,
    )
    if api_call:
        lines = code.splitlines(keepends=True)
        char_pos = 0
        api_line_idx = 0
        for idx, line in enumerate(lines):
            next_pos = char_pos + len(line)
            if char_pos <= api_call.start() < next_pos:
                api_line_idx = idx
                break
            char_pos = next_pos
        for idx in range(api_line_idx + 1, len(lines)):
            if re.match(rf"^{re.escape(call_indent)}if err != nil \{{", lines[idx]):
                brace_depth = 0
                for end_idx in range(idx, len(lines)):
                    brace_depth += lines[end_idx].count("{")
                    brace_depth -= lines[end_idx].count("}")
                    if brace_depth == 0:
                        lines.insert(end_idx + 1, f"{call_indent}fmt.Println(resp)\n")
                        return "".join(lines)
                break
    return code


def add_java_response_print(code: str) -> str:
    if "System.out.println(resp);" in code:
        return code
    pattern = re.compile(r"^(\s*)(api\.[A-Za-z_][A-Za-z0-9_]*\([^;\n]*\);)(\s*)$", re.MULTILINE)

    def repl(match: re.Match[str]) -> str:
        indent = match.group(1)
        call = match.group(2)[:-1]
        return f"{indent}Object resp = {call};\n{indent}System.out.println(resp);"

    return pattern.sub(repl, code, count=1)


def add_php_response_print(code: str) -> str:
    if "print_r($response);" in code:
        return code
    pattern = re.compile(r"^(\s*)(\$apiInstance->[A-Za-z_][A-Za-z0-9_]*\([^;\n]*\);)(\s*)$", re.MULTILINE)

    def repl(match: re.Match[str]) -> str:
        indent = match.group(1)
        call = match.group(2)[:-1]
        return f"{indent}$response = {call};\n{indent}print_r($response);"

    return pattern.sub(repl, code, count=1)


def add_response_print(language: str, code: Any) -> Any:
    if isinstance(code, dict):
        return {key: add_response_print(language, value) for key, value in code.items()}
    if not isinstance(code, str) or not code:
        return code
    lang = language.upper()
    if lang == "PYTHON":
        return add_python_response_print(code)
    if lang == "GO":
        return add_go_response_print(code)
    if lang == "JAVA":
        return add_java_response_print(code)
    if lang == "PHP":
        return add_php_response_print(code)
    return code


def scrub_unusable_json_examples(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: scrub_unusable_json_examples(item) for key, item in value.items()}
    if isinstance(value, list):
        return [scrub_unusable_json_examples(item) for item in value]
    if isinstance(value, str):
        return scrub_unusable_json_example_text(value)
    return value


def scrub_unusable_json_example_text(value: str) -> str:
    value = re.sub(
        r"['\"]?[A-Za-z][A-Za-z0-9_]*\.\d+\.[A-Za-z0-9_]+\s*=\s*[^'\"\s&]+(?:&[A-Za-z][A-Za-z0-9_]*\.\d+\.[A-Za-z0-9_]+\s*=\s*[^'\"\s&]+)*['\"]?",
        "1",
        value,
    )
    return value


def format_code_result(
    response: dict[str, Any],
    language: str | None,
    mocked_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = response.get("Result") or {}
    demo_sdk = result.get("DemoSdk") or {}
    normalized = {str(k).upper(): v for k, v in demo_sdk.items()}
    normalized = {
        key: add_response_print(key, value)
        for key, value in normalized.items()
    }
    normalized = scrub_unusable_json_examples(normalized)
    if mocked_params:
        normalized = {
            key: annotate_mocked_code(key, value, mocked_params)
            for key, value in normalized.items()
        }
    selected = normalize_language(language)
    if selected:
        return {
            "available_languages": sorted(normalized.keys()),
            "selected_language": selected,
            "code": normalized.get(selected),
            "raw_demo_sdk": normalized,
        }
    return {
        "available_languages": sorted(normalized.keys()),
        "selected_language": None,
        "raw_demo_sdk": normalized,
    }


def mock_notice(mocked_params: dict[str, Any]) -> str:
    names = ", ".join(sorted(mocked_params))
    return f"必填参数 {names} 使用了 mock 值，调用 API 前请替换为真实值。"


def snake_case(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    value = re.sub(r"[^A-Za-z0-9]+", "_", value)
    return value.strip("_").lower()


def append_line_comment(line: str, comment: str) -> str:
    newline = "\n" if line.endswith("\n") else ""
    body = line[:-1] if newline else line
    if comment in body:
        return line
    return f"{body} {comment}{newline}"


def mock_literal_candidates(mock_value: Any) -> list[str]:
    if isinstance(mock_value, str):
        return [mock_value]
    if isinstance(mock_value, bool):
        return [str(mock_value), str(mock_value).lower()]
    if isinstance(mock_value, (int, float)):
        return [str(mock_value)]
    return []


def line_assigns_mocked_param(language: str, line: str, param_name: str) -> bool:
    lang = language.upper()
    if lang == "PYTHON":
        return bool(re.search(rf"\b{re.escape(snake_case(param_name))}\s*=", line))
    if lang == "GO":
        return bool(re.search(rf"\b{re.escape(param_name)}\s*:", line))
    if lang == "NODEJS":
        return bool(re.search(rf"\b{re.escape(param_name)}\s*:", line))
    if lang == "JAVA":
        return f"set{param_name}(" in line
    if lang == "PHP":
        return f"set{param_name}(" in line
    return False


def mocked_annotation_items(param_name: str, mock_value: Any) -> list[tuple[str, Any]]:
    items: list[tuple[str, Any]] = [(param_name, mock_value)]
    if isinstance(mock_value, dict):
        for child_name, child_value in mock_value.items():
            items.extend(mocked_annotation_items(str(child_name), child_value))
    elif isinstance(mock_value, list):
        for child_value in mock_value:
            if isinstance(child_value, dict):
                for child_name, nested_value in child_value.items():
                    items.extend(mocked_annotation_items(str(child_name), nested_value))
            elif child_value not in (None, ""):
                items.append((param_name, child_value))
    return items


def annotate_mocked_assignment_line(language: str, line: str, param_name: str, mock_value: Any) -> str:
    candidates = mock_literal_candidates(mock_value)
    lang = language.upper()
    assigns_param = line_assigns_mocked_param(language, line, param_name)
    if candidates and not any(candidate in line for candidate in candidates):
        return line
    if not candidates and not assigns_param:
        return line
    if lang == "PYTHON" and assigns_param:
        return append_line_comment(line, "# mock 值，调用前请替换")
    if lang == "GO" and assigns_param:
        return append_line_comment(line, "// mock 值，调用前请替换")
    if lang == "JAVA" and assigns_param:
        return append_line_comment(line, "// mock 值，调用前请替换")
    if lang == "PHP" and assigns_param:
        return append_line_comment(line, "// mock 值，调用前请替换")
    if lang == "NODEJS" and assigns_param:
        return append_line_comment(line, "// mock 值，调用前请替换")
    if lang == "CURL":
        return line
    return line


def annotate_mocked_code(language: str, code: Any, mocked_params: dict[str, Any]) -> Any:
    if isinstance(code, dict):
        return {k: annotate_mocked_code(language, v, mocked_params) for k, v in code.items()}
    if not isinstance(code, str) or not code:
        return code

    lines = code.splitlines(keepends=True)
    annotation_items: list[tuple[str, Any]] = []
    for param_name, mock_value in mocked_params.items():
        annotation_items.extend(mocked_annotation_items(param_name, mock_value))
    for idx, line in enumerate(lines):
        for param_name, mock_value in annotation_items:
            line = annotate_mocked_assignment_line(language, line, param_name, mock_value)
        lines[idx] = line
    return "".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service-code")
    parser.add_argument("--api-version", "--version", dest="api_version")
    parser.add_argument("--action")
    parser.add_argument("--region")
    parser.add_argument("--language")
    parser.add_argument("--params-json")
    parser.add_argument("--params-file")
    parser.add_argument("--x-language", default="zh")
    parser.add_argument("--refresh-swagger", action="store_true")
    parser.add_argument("--output", choices=("json", "text"), default="json")
    args = parser.parse_args()

    identifiers = {
        "service_code": args.service_code,
        "api_version": args.api_version,
        "action": args.action,
    }
    missing = [name for name, value in identifiers.items() if not value]
    if missing:
        print_json(
            {
                "error": "missing_api_identifiers",
                "message": "Direct mode requires --service-code, --api-version, and --action.",
                "missing": missing,
            }
        )
        return 2

    params = load_params(args)
    record = build_direct_record(
        service_code=args.service_code,
        api_version=args.api_version,
        action=args.action,
    )
    swagger = fetch_swagger(
        record,
        x_language=args.x_language,
        refresh=args.refresh_swagger,
    )
    info = swagger_info(swagger)
    record["name_cn"] = str(info.get("title") or info.get("description") or "")
    payload, param_info = make_payload(record, swagger, params, args.region)
    final_params, mocked_params = apply_missing_required_mocks(params, param_info)
    payload["Params"] = final_params
    unknown = [name for name in params if name not in param_info["known_params"]]

    response = call_make_code(payload, x_language=args.x_language)
    code_result = format_code_result(response, args.language, mocked_params)
    output = {
        "api": record,
        "payload": payload,
        "warnings": {
            "unknown_params": unknown,
            "mocked_required_params": mocked_params,
            "mock_notice": mock_notice(mocked_params) if mocked_params else "",
        },
        **code_result,
    }
    if args.output == "text":
        print_text(output)
    else:
        print_json(output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print_json({"error": "exception", "message": str(exc)})
        raise SystemExit(1)
