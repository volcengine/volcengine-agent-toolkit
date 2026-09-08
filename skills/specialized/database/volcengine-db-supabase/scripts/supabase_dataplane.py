#!/usr/bin/env python3
# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: MIT
"""Supabase data-plane operations not exposed by `ve aidap`."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import quote, urlencode


DATABASE_ACTIONS = {
    "execute-sql",
    "list-tables",
    "list-migrations",
    "list-extensions",
    "apply-migration",
    "generate-typescript-types",
}
EDGE_ACTIONS = {
    "list-edge-functions",
    "get-edge-function",
    "deploy-edge-function",
    "delete-edge-function",
}
STORAGE_ACTIONS = {
    "list-storage-buckets",
    "create-storage-bucket",
    "delete-storage-bucket",
    "get-storage-config",
}
WRITE_ACTIONS = {
    "apply-migration",
    "deploy-edge-function",
    "delete-edge-function",
    "create-storage-bucket",
    "delete-storage-bucket",
}

RUNTIME_CONFIG = {
    "native-node20/v1": {"entrypoint": "index.ts", "extensions": [".ts", ".js"]},
    "native-python3.9/v1": {"entrypoint": "app.py", "extensions": [".py"]},
    "native-python3.10/v1": {"entrypoint": "app.py", "extensions": [".py"]},
    "native-python3.12/v1": {"entrypoint": "app.py", "extensions": [".py"]},
}
MAX_CODE_SIZE = 10 * 1024 * 1024


class DataPlaneError(RuntimeError):
    pass


class SupabaseApiError(DataPlaneError):
    def __init__(self, status_code: int, path: str, endpoint: str, payload: Any):
        self.status_code = status_code
        self.path = path
        self.endpoint = endpoint
        self.payload = payload
        super().__init__(
            json.dumps(
                {
                    "status_code": status_code,
                    "path": path,
                    "endpoint": endpoint,
                    "error": payload,
                },
                ensure_ascii=False,
            )
        )


def env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def read_text(value: str | None, file_path: str | None, label: str) -> str:
    if value and file_path:
        raise DataPlaneError(f"{label} and {label}-file cannot be used together")
    if file_path:
        return Path(file_path).read_text(encoding="utf-8")
    if value:
        return value
    raise DataPlaneError(f"{label} or {label}-file is required")


def to_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


def parse_json_object(value: str | None, label: str) -> dict[str, Any]:
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise DataPlaneError(f"invalid JSON for {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise DataPlaneError(f"{label} must be a JSON object")
    return payload


def find_json_payload(text: str) -> Any:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char not in "[{":
            continue
        try:
            payload, _ = decoder.raw_decode(text[index:])
            return payload
        except json.JSONDecodeError:
            continue
    raise DataPlaneError("could not parse JSON from ve output")


def run_ve_aidap(action: str, body: dict[str, Any], region: str | None = None) -> Any:
    cmd = ["ve", "aidap", action]
    if body:
        cmd.extend(["--body", json.dumps(body, separators=(",", ":"), ensure_ascii=False)])
    if region:
        cmd.extend(["---region", region])
    completed = subprocess.run(cmd, check=False, text=True, capture_output=True)
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    if completed.returncode != 0:
        raise DataPlaneError(f"ve aidap {action} failed: {output.strip()}")
    payload = find_json_payload(output)
    if isinstance(payload, dict) and "Result" in payload:
        return payload["Result"]
    return payload


def pick(source: Any, *field_names: str) -> Any:
    if not isinstance(source, dict):
        return None
    lowered = {str(key).lower(): value for key, value in source.items()}
    for field_name in field_names:
        value = source.get(field_name)
        if value is None:
            value = lowered.get(field_name.lower())
        if isinstance(value, str):
            value = value.strip() or None
        if value is not None:
            return value
    return None


def walk(value: Any) -> list[Any]:
    result = [value]
    if isinstance(value, dict):
        for item in value.values():
            result.extend(walk(item))
    elif isinstance(value, list):
        for item in value:
            result.extend(walk(item))
    return result


def dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in walk(value) if isinstance(item, dict)]


def strings(value: Any) -> list[str]:
    return [item.strip() for item in walk(value) if isinstance(item, str) and item.strip()]


def looks_like_branch_id(value: str | None) -> bool:
    return bool(value and value.strip().startswith("br-"))


def normalize_endpoint(value: str, scheme: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    if text.startswith(("http://", "https://")):
        return text.rstrip("/")
    if " " in text or "/" in text or "." not in text:
        return None
    if scheme == "http":
        return f"http://{text}:80"
    return f"https://{text}"


def extract_endpoint(payload: Any, scheme: str) -> str:
    scheme = (scheme or "http").strip().lower() or "http"
    preferred: list[str] = []
    fallback: list[str] = []
    for item in strings(payload):
        endpoint = normalize_endpoint(item, scheme)
        if not endpoint:
            continue
        if "volces.com" in endpoint and "ivolces.com" not in endpoint:
            preferred.append(endpoint)
        else:
            fallback.append(endpoint)
    if preferred:
        return preferred[0]
    if fallback:
        return fallback[0]
    raise DataPlaneError("could not find Supabase endpoint in ve response")


def extract_branch_id(payload: Any) -> str | None:
    for item in dicts(payload):
        branch_id = pick(item, "BranchId", "branch_id", "Id", "id")
        if isinstance(branch_id, str) and looks_like_branch_id(branch_id):
            return branch_id
    for item in strings(payload):
        if looks_like_branch_id(item):
            return item
    return None


def extract_workspace_ids(payload: Any) -> list[str]:
    workspace_ids: list[str] = []
    for item in dicts(payload):
        workspace_id = pick(item, "WorkspaceId", "workspace_id", "Id", "id")
        if isinstance(workspace_id, str) and workspace_id and workspace_id not in workspace_ids:
            workspace_ids.append(workspace_id)
    return workspace_ids


def extract_api_key(payload: Any, preferred_type: str = "service") -> str:
    candidates: list[tuple[int, str]] = []
    for item in dicts(payload):
        key_value = pick(item, "Key", "key", "ApiKey", "api_key", "APIKey", "Value", "value")
        if not isinstance(key_value, str) or len(key_value) < 16:
            continue
        key_type = str(pick(item, "Type", "type", "KeyType", "key_type", "Name", "name") or "").lower()
        score = 0
        if preferred_type.lower() in key_type or "service_role" in key_type:
            score = 10
        elif "service" in key_type:
            score = 8
        elif "public" in key_type or "anon" in key_type:
            score = 1
        candidates.append((score, key_value))
    if not candidates:
        raise DataPlaneError("could not find API key in ve response")
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def resolve_workspace_for_branch(branch_id: str, region: str | None = None) -> str:
    workspaces = run_ve_aidap("DescribeWorkspaces", {"Limit": 100}, region)
    for workspace_id in extract_workspace_ids(workspaces):
        branches = run_ve_aidap("DescribeBranches", {"WorkspaceId": workspace_id}, region)
        for item in dicts(branches):
            if pick(item, "BranchId", "branch_id", "Id", "id") == branch_id:
                return workspace_id
    raise DataPlaneError(f"could not resolve workspace for branch {branch_id}")


def resolve_workspace_and_branch(args: argparse.Namespace) -> tuple[str | None, str | None]:
    workspace_id = args.workspace_id or args.default_workspace_id or env("DEFAULT_WORKSPACE_ID")
    branch_id = args.branch_id
    if workspace_id and looks_like_branch_id(workspace_id):
        branch_id = workspace_id
        workspace_id = resolve_workspace_for_branch(branch_id, args.region)
    if workspace_id and not branch_id:
        payload = run_ve_aidap("DescribeDefaultBranch", {"WorkspaceId": workspace_id}, args.region)
        branch_id = extract_branch_id(payload)
    return workspace_id, branch_id


def resolve_endpoint_and_key(args: argparse.Namespace) -> tuple[str, str, str | None, str | None]:
    endpoint = env("SUPABASE_URL")
    key = env("SUPABASE_SERVICE_ROLE_KEY")
    workspace_id: str | None = None
    branch_id: str | None = args.branch_id

    if not endpoint or not key:
        workspace_id, branch_id = resolve_workspace_and_branch(args)
        if not workspace_id:
            raise DataPlaneError(
                "workspace_id is required unless SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set"
            )
    if not endpoint:
        endpoint_payload = run_ve_aidap(
            "DescribeWorkspaceEndpoint",
            {"WorkspaceId": workspace_id, "BranchId": branch_id},
            args.region,
        )
        endpoint = extract_endpoint(endpoint_payload, args.endpoint_scheme)
    if not key:
        key_payload = run_ve_aidap(
            "DescribeAPIKeys",
            {"WorkspaceId": workspace_id, "BranchId": branch_id, "Limit": 100},
            args.region,
        )
        key = extract_api_key(key_payload, "service")
    return endpoint.rstrip("/"), key, workspace_id, branch_id


def call_supabase_api(
    endpoint: str,
    api_key: str,
    path: str,
    method: str = "GET",
    json_data: Any | None = None,
    params: dict[str, Any] | None = None,
    content: bytes | None = None,
    timeout: float = 30.0,
) -> Any:
    url = f"{endpoint}{path}"
    if params:
        url = f"{url}?{urlencode(params, doseq=True)}"
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
    }
    data = content
    if json_data is not None:
        data = json.dumps(json_data, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    for attempt in range(3):
        req = urllib_request.Request(url=url, data=data, headers=headers, method=method)
        try:
            with urllib_request.urlopen(req, timeout=timeout) as response:
                raw = response.read()
                if response.status == 204 or not raw:
                    return {"success": True}
                text = raw.decode("utf-8")
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    return json.loads(text)
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"raw": text}
        except urllib_error.HTTPError as exc:
            payload: Any
            text = exc.read().decode("utf-8")
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                payload = text
            if exc.code in {502, 503, 504} and attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise SupabaseApiError(exc.code, path, endpoint, payload) from exc
        except urllib_error.URLError as exc:
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise DataPlaneError(f"{exc.reason} [endpoint: {endpoint}, path: {path}]") from exc
    raise DataPlaneError(f"request failed [endpoint: {endpoint}, path: {path}]")


class DataPlaneClient:
    def __init__(self, endpoint: str, api_key: str, workspace_slug: str = "default"):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.workspace_slug = workspace_slug.strip() or "default"

    def call_api(self, path: str, method: str = "GET", json_data: Any | None = None, params: dict[str, Any] | None = None) -> Any:
        return call_supabase_api(self.endpoint, self.api_key, path, method=method, json_data=json_data, params=params)

    def execute_sql_raw(self, query: str) -> list[dict[str, Any]]:
        if not query or not query.strip():
            raise DataPlaneError("SQL query cannot be empty")
        result = self.call_api("/pg/query", method="POST", json_data={"query": query})
        if isinstance(result, dict) and isinstance(result.get("data"), list):
            result = result["data"]
        if not isinstance(result, list):
            raise DataPlaneError(f"unexpected SQL result type: {type(result).__name__}")
        return result

    def list_edge_functions(self) -> Any:
        return self.call_api(f"/v1/projects/{quote(self.workspace_slug, safe='')}/functions")

    def get_edge_function(self, function_name: str) -> Any:
        encoded_name = quote(function_name, safe="")
        result = self.call_api(f"/v1/projects/{quote(self.workspace_slug, safe='')}/functions/{encoded_name}")
        return normalize_function_payload(result)

    def deploy_edge_function(
        self,
        function_name: str,
        source_code: str,
        verify_jwt: bool,
        runtime: str,
        import_map: str | None = None,
    ) -> Any:
        data = build_deployment_payload(runtime, source_code, verify_jwt, function_name)
        if import_map:
            try:
                import_map_data = json.loads(import_map)
            except json.JSONDecodeError as exc:
                raise DataPlaneError(f"invalid import map JSON: {exc}") from exc
            data["metadata"]["import_map_path"] = "import_map.json"
            data["files"].append({"name": "import_map.json", "content": json.dumps(import_map_data)})
        encoded_name = quote(function_name, safe="")
        result = self.call_api(
            f"/v1/projects/{quote(self.workspace_slug, safe='')}/functions/deploy",
            method="POST",
            params={"slug": encoded_name},
            json_data=data,
        )
        if isinstance(result, dict) and not result.get("runtime"):
            result["runtime"] = runtime
        return result

    def delete_edge_function(self, function_name: str) -> dict[str, Any]:
        encoded_name = quote(function_name, safe="")
        self.call_api(f"/v1/projects/{quote(self.workspace_slug, safe='')}/functions/{encoded_name}", method="DELETE")
        return {"success": True, "message": "Edge function deleted successfully"}

    def list_storage_buckets(self) -> Any:
        return self.call_api("/storage/v1/bucket")

    def create_storage_bucket(
        self,
        bucket_name: str,
        public: bool,
        file_size_limit: int | None,
        allowed_mime_types: str | list[str] | None,
    ) -> Any:
        if not bucket_name or not bucket_name.strip():
            raise DataPlaneError("Bucket name cannot be empty")
        data: dict[str, Any] = {"name": bucket_name, "public": public}
        if file_size_limit:
            data["file_size_limit"] = file_size_limit
        normalized_mime_types = normalize_allowed_mime_types(allowed_mime_types)
        if normalized_mime_types:
            data["allowed_mime_types"] = normalized_mime_types
        return self.call_api("/storage/v1/bucket", method="POST", json_data=data)

    def delete_storage_bucket(self, bucket_name: str) -> dict[str, Any]:
        if not bucket_name or not bucket_name.strip():
            raise DataPlaneError("Bucket name cannot be empty")
        encoded_bucket = quote(bucket_name, safe="")
        response = self.call_api(f"/storage/v1/bucket/{encoded_bucket}", method="DELETE")
        if isinstance(response, dict) and response.get("error"):
            raise DataPlaneError(str(response["error"]))
        return {"success": True, "message": "Bucket deleted successfully"}

    def get_storage_config(self) -> Any:
        return self.call_api("/storage/v1/config")


def needs_handler_wrapper(runtime: str, source_code: str) -> bool:
    if runtime != "native-node20/v1":
        return False
    if "Deno.serve" in source_code:
        return False
    return "export default function" in source_code or "export default async function" in source_code or "export default (" in source_code


def validate_runtime(runtime: str) -> None:
    if runtime not in RUNTIME_CONFIG:
        available = ", ".join(RUNTIME_CONFIG)
        raise DataPlaneError(f"unsupported runtime '{runtime}'. Available: {available}")


def build_deployment_payload(runtime: str, source_code: str, verify_jwt: bool, function_name: str) -> dict[str, Any]:
    validate_runtime(runtime)
    if not source_code or not source_code.strip():
        raise DataPlaneError("Source code cannot be empty")
    source_code = source_code.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    code_size = len(source_code.encode("utf-8"))
    if code_size > MAX_CODE_SIZE:
        raise DataPlaneError(f"Source code too large: {code_size} bytes (max {MAX_CODE_SIZE} bytes)")
    entrypoint = RUNTIME_CONFIG[runtime]["entrypoint"]
    files = [{"name": entrypoint, "content": source_code}]
    if needs_handler_wrapper(runtime, source_code):
        files = [
            {"name": "handler.ts", "content": source_code},
            {"name": entrypoint, "content": "import handler from './handler.ts'\nDeno.serve((req) => handler(req))\n"},
        ]
    return {
        "metadata": {
            "name": function_name,
            "slug": function_name,
            "entrypoint_path": entrypoint,
            "verify_jwt": verify_jwt,
        },
        "files": files,
    }


def normalize_function_payload(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    result = dict(payload)
    files = result.get("files")
    entrypoint_path = result.get("entrypoint_path")
    if isinstance(files, list):
        source_code = None
        for file_info in files:
            if not isinstance(file_info, dict):
                continue
            if entrypoint_path and file_info.get("name") == entrypoint_path and isinstance(file_info.get("content"), str):
                source_code = file_info.get("content")
                break
            if source_code is None and isinstance(file_info.get("content"), str):
                source_code = file_info.get("content")
        if source_code is not None:
            result["source_code"] = source_code
    return result


def normalize_allowed_mime_types(allowed_mime_types: str | list[str] | None) -> list[str] | None:
    if allowed_mime_types is None:
        return None
    if isinstance(allowed_mime_types, list):
        values = allowed_mime_types
    elif isinstance(allowed_mime_types, str):
        text = allowed_mime_types.strip()
        if not text:
            return None
        if text.startswith("["):
            parsed = json.loads(text)
            if not isinstance(parsed, list):
                raise DataPlaneError("allowed_mime_types JSON value must be a list of strings")
            values = parsed
        else:
            values = text.split(",")
    else:
        raise DataPlaneError("allowed_mime_types must be a string, JSON array string, or list of strings")
    result = [value.strip() for value in values if isinstance(value, str) and value.strip()]
    return result or None


def to_ts_type(data_type: str, udt_name: str) -> str:
    normalized_data_type = (data_type or "").lower()
    normalized_udt_name = (udt_name or "").lower()
    if normalized_data_type in {"smallint", "integer", "bigint", "numeric", "decimal", "real", "double precision"}:
        return "number"
    if normalized_data_type == "boolean":
        return "boolean"
    if normalized_data_type in {"json", "jsonb"}:
        return "Json"
    if normalized_data_type in {"date", "timestamp without time zone", "timestamp with time zone", "time without time zone", "time with time zone"}:
        return "string"
    if normalized_data_type == "bytea":
        return "string"
    if normalized_data_type == "array":
        base = normalized_udt_name[1:] if normalized_udt_name.startswith("_") else normalized_udt_name
        return f"{to_ts_type(base, base)}[]"
    if normalized_udt_name in {"uuid", "varchar", "text", "bpchar", "name", "citext", "inet"}:
        return "string"
    if normalized_udt_name in {"int2", "int4", "int8", "float4", "float8"}:
        return "number"
    if normalized_udt_name == "bool":
        return "boolean"
    if normalized_udt_name in {"json", "jsonb"}:
        return "Json"
    return "string"


def to_ts_key(key: str) -> str:
    if key and key.replace("_", "").isalnum() and not key[0].isdigit():
        return key
    escaped = key.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def build_typescript_types(columns: list[dict[str, Any]]) -> str:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for column in columns:
        schema_name = column.get("table_schema")
        table_name = column.get("table_name")
        if not schema_name or not table_name:
            continue
        grouped.setdefault(str(schema_name), {}).setdefault(str(table_name), []).append(column)

    lines = [
        "export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[]",
        "",
        "export type Database = {",
    ]
    for schema_name in sorted(grouped):
        tables = grouped[schema_name]
        lines.append(f"  {to_ts_key(schema_name)}: {{")
        lines.append("    Tables: {")
        for table_name in sorted(tables):
            table_columns = tables[table_name]
            lines.append(f"      {to_ts_key(table_name)}: {{")
            lines.append("        Row: {")
            for column in table_columns:
                col_name = str(column.get("column_name"))
                base_type = to_ts_type(str(column.get("data_type", "")), str(column.get("udt_name", "")))
                nullable = column.get("is_nullable") == "YES"
                row_type = f"{base_type} | null" if nullable else base_type
                lines.append(f"          {to_ts_key(col_name)}: {row_type}")
            lines.append("        }")
            lines.append("        Insert: {")
            for column in table_columns:
                col_name = str(column.get("column_name"))
                base_type = to_ts_type(str(column.get("data_type", "")), str(column.get("udt_name", "")))
                nullable = column.get("is_nullable") == "YES"
                has_default = column.get("column_default") is not None
                is_identity = column.get("is_identity") == "YES"
                optional = nullable or has_default or is_identity
                insert_type = f"{base_type} | null" if nullable else base_type
                suffix = "?" if optional else ""
                lines.append(f"          {to_ts_key(col_name)}{suffix}: {insert_type}")
            lines.append("        }")
            lines.append("        Update: {")
            for column in table_columns:
                col_name = str(column.get("column_name"))
                base_type = to_ts_type(str(column.get("data_type", "")), str(column.get("udt_name", "")))
                nullable = column.get("is_nullable") == "YES"
                update_type = f"{base_type} | null" if nullable else base_type
                lines.append(f"          {to_ts_key(col_name)}?: {update_type}")
            lines.append("        }")
            lines.append("      }")
        lines.append("    }")
        lines.append("    Views: {}")
        lines.append("    Functions: {}")
        lines.append("    Enums: {}")
        lines.append("    CompositeTypes: {}")
        lines.append("  }")
    lines.append("}")
    return "\n".join(lines)


def validate_schemas(schemas: list[str]) -> None:
    for schema in schemas:
        if not schema.replace("_", "").isalnum():
            raise DataPlaneError(f"Invalid schema name: {schema}")


def execute_action(client: DataPlaneClient, args: argparse.Namespace) -> Any:
    action = args.action
    if action == "execute-sql":
        query = read_text(args.query, args.query_file, "--query")
        return client.execute_sql_raw(query)
    if action == "list-tables":
        schemas = [schema.strip() for schema in args.schemas.split(",") if schema.strip()]
        validate_schemas(schemas)
        schema_list = "', '".join(schemas)
        query = f"""
        SELECT schemaname as schema, tablename as name
        FROM pg_tables
        WHERE schemaname IN ('{schema_list}')
        ORDER BY schemaname, tablename
        """
        return client.execute_sql_raw(query)
    if action == "list-migrations":
        query = """
        CREATE SCHEMA IF NOT EXISTS supabase_migrations;
        CREATE TABLE IF NOT EXISTS supabase_migrations.schema_migrations (
            version text PRIMARY KEY,
            name text NOT NULL,
            inserted_at timestamptz NOT NULL DEFAULT now()
        );
        SELECT version, name
        FROM supabase_migrations.schema_migrations
        ORDER BY version DESC
        """
        return client.execute_sql_raw(query)
    if action == "list-extensions":
        query = """
        SELECT e.extname AS name, n.nspname AS schema, e.extversion AS version
        FROM pg_extension e
        JOIN pg_namespace n ON n.oid = e.extnamespace
        ORDER BY e.extname
        """
        return client.execute_sql_raw(query)
    if action == "apply-migration":
        name = (args.name or "").strip()
        if not name:
            raise DataPlaneError("--name is required")
        query = read_text(args.query, args.query_file, "--query")
        migration_name = name.replace("'", "''")
        migration_version = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S%f")
        migration_sql = f"""
        BEGIN;
        CREATE SCHEMA IF NOT EXISTS supabase_migrations;
        CREATE TABLE IF NOT EXISTS supabase_migrations.schema_migrations (
            version text PRIMARY KEY,
            name text NOT NULL,
            inserted_at timestamptz NOT NULL DEFAULT now()
        );
        {query}
        INSERT INTO supabase_migrations.schema_migrations (version, name)
        VALUES ('{migration_version}', '{migration_name}')
        ON CONFLICT (version) DO UPDATE SET name = EXCLUDED.name;
        COMMIT;
        """
        client.execute_sql_raw(migration_sql)
        return {
            "success": True,
            "message": f"Migration {name} applied successfully",
            "version": migration_version,
            "name": name,
        }
    if action == "generate-typescript-types":
        schemas = [schema.strip() for schema in args.schemas.split(",") if schema.strip()]
        validate_schemas(schemas)
        schema_list = "', '".join(schemas)
        query = f"""
        SELECT table_schema, table_name, column_name, is_nullable, is_identity, data_type, udt_name, column_default
        FROM information_schema.columns
        WHERE table_schema IN ('{schema_list}')
        ORDER BY table_schema, table_name, ordinal_position
        """
        return build_typescript_types(client.execute_sql_raw(query))

    if action == "list-edge-functions":
        return client.list_edge_functions()
    if action == "get-edge-function":
        if not args.function_name:
            raise DataPlaneError("--function-name is required")
        return client.get_edge_function(args.function_name)
    if action == "deploy-edge-function":
        if not args.function_name:
            raise DataPlaneError("--function-name is required")
        source_code = read_text(args.source_code, args.source_file, "--source-code")
        import_map = read_text(args.import_map, args.import_map_file, "--import-map") if args.import_map or args.import_map_file else None
        return client.deploy_edge_function(args.function_name, source_code, args.verify_jwt, args.runtime, import_map)
    if action == "delete-edge-function":
        if not args.function_name:
            raise DataPlaneError("--function-name is required")
        return client.delete_edge_function(args.function_name)

    if action == "list-storage-buckets":
        return client.list_storage_buckets()
    if action == "create-storage-bucket":
        if not args.bucket_name:
            raise DataPlaneError("--bucket-name is required")
        return client.create_storage_bucket(args.bucket_name, args.public, args.file_size_limit, args.allowed_mime_types)
    if action == "delete-storage-bucket":
        if not args.bucket_name:
            raise DataPlaneError("--bucket-name is required")
        return client.delete_storage_bucket(args.bucket_name)
    if action == "get-storage-config":
        return client.get_storage_config()

    supported = sorted(DATABASE_ACTIONS | EDGE_ACTIONS | STORAGE_ACTIONS)
    raise DataPlaneError(f"Unsupported action: {action}. Available actions: {', '.join(supported)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("action", choices=sorted(DATABASE_ACTIONS | EDGE_ACTIONS | STORAGE_ACTIONS))
    parser.add_argument("--workspace-id", help="Workspace ID, or branch ID for compatibility with the old skill")
    parser.add_argument("--branch-id", help="Branch ID. Defaults to the workspace default branch")
    parser.add_argument("--default-workspace-id", default=env("DEFAULT_WORKSPACE_ID"))
    parser.add_argument("--region", help="Region passed to ve as ---region")
    parser.add_argument("--endpoint-scheme", default=env("SUPABASE_ENDPOINT_SCHEME", "http"))
    parser.add_argument("--workspace-slug", default=env("SUPABASE_WORKSPACE_SLUG", "default"))

    parser.add_argument("--query")
    parser.add_argument("--query-file")
    parser.add_argument("--schemas", default="public")
    parser.add_argument("--name")

    parser.add_argument("--function-name")
    parser.add_argument("--source-code")
    parser.add_argument("--source-file")
    parser.add_argument("--verify-jwt", dest="verify_jwt", action="store_true", default=True)
    parser.add_argument("--no-verify-jwt", dest="verify_jwt", action="store_false")
    parser.add_argument("--runtime", default="native-node20/v1")
    parser.add_argument("--import-map")
    parser.add_argument("--import-map-file")

    parser.add_argument("--bucket-name")
    parser.add_argument("--public", action="store_true")
    parser.add_argument("--file-size-limit", type=int)
    parser.add_argument("--allowed-mime-types")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.action in WRITE_ACTIONS and str(env("READ_ONLY", "false")).lower() == "true":
        print(to_json({"error": f"Cannot execute {args.action} in read-only mode"}))
        return 1
    try:
        endpoint, api_key, _, _ = resolve_endpoint_and_key(args)
        client = DataPlaneClient(endpoint, api_key, args.workspace_slug)
        result = execute_action(client, args)
        print(result if isinstance(result, str) else to_json(result))
        return 0
    except Exception as exc:
        message = str(exc) if str(exc) else type(exc).__name__
        print(to_json({"error": message}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
