#!/usr/bin/env python3
# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: MIT
"""
Call Volcengine OpenAPIs whose request shape `ve` cannot express.

`ve <service> <Action> --version <v> --endpoint <host> --force` handles any
Action/Version API, including ones missing from the CLI metadata. What it
cannot do is send URL query parameters *and* a request body in one POST
(`--body` excludes flattened parameters, and the body is JSON only). A few
services need exactly that:

  * VMP Prometheus-compatible APIs: `workspace` in the query string, PromQL
    fields as an application/x-www-form-urlencoded body.
  * Flink GWS APIs: `ProjectId` (and friends) in the query string, the rest
    as a JSON body.

This helper signs and sends those. It has two modes:

  registry   --api <Name>            known query/body split (see --list)
  free       --api <Name> --service <svc> --version <ver> --query-keys k1,k2
                                     any other API with the same problem

Credentials come from VOLCENGINE_ACCESS_KEY/VOLCENGINE_SECRET_KEY, else from
the `ve` config/login cache (see references/extend-api-helper.md). Signing is inline
on purpose so the script has no third-party imports.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import hmac
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import quote, urlencode


DEFAULT_REGION = "cn-beijing"
DEFAULT_HOST = "open.volcengineapi.com"
CLI_CONFIG_FILE_ENV = "VOLCENGINE_CLI_CONFIG_FILE"
LOGIN_CACHE_DIRECTORY_ENV = "VOLCENGINE_LOGIN_CACHE_DIRECTORY"
FORM_CONTENT_TYPE = "application/x-www-form-urlencoded"
JSON_CONTENT_TYPE = "application/json"


@dataclass(frozen=True)
class ResolvedCredentials:
    ak: str
    sk: str
    session_token: str = ""
    provider_name: str = ""


class CredentialResolutionError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Registry: only APIs that need query + body in one request. Anything else
# belongs to `ve ... --force`, not here.
# ---------------------------------------------------------------------------
API_REGISTRY: list[dict[str, Any]] = []


def _register(
    names: list[str],
    *,
    service: str,
    version: str,
    query_keys: list[str],
    summary: str,
    content_type: str = JSON_CONTENT_TYPE,
    host: str | None = None,
    host_template: str | None = None,
    preserve_query_keys_in_body: list[str] | None = None,
) -> None:
    for name in names:
        entry: dict[str, Any] = {
            "name": name,
            "service": service,
            "version": version,
            "method": "POST",
            "content_type": content_type,
            "query_keys": list(query_keys),
            "summary": f"{summary}: {name}.",
        }
        if host:
            entry["host"] = host
        if host_template:
            entry["host_template"] = host_template
        if preserve_query_keys_in_body:
            entry["preserve_query_keys_in_body"] = list(preserve_query_keys_in_body)
        API_REGISTRY.append(entry)


_VMP = dict(
    service="vmp",
    version="2021-03-03",
    content_type=FORM_CONTENT_TYPE,
    host_template="vmp.{region}.volcengineapi.com",
    summary="VMP Prometheus-compatible query (workspace in query string, form body)",
)
_register(["QueryMetrics", "QueryMetricsRange", "GetLabels", "GetSeries"], query_keys=["workspace"], **_VMP)
_register(["GetLabelValues"], query_keys=["workspace", "label"], **_VMP)

_FLINK = dict(
    service="flink",
    version="2021-06-01",
    host=DEFAULT_HOST,
    summary="Flink GWS operation (ProjectId in query string, JSON body)",
)
_register(["ListGWSDirectory"], query_keys=["ProjectId", "Type"], **_FLINK)
_register(
    [
        "GetGWSApplicationDraft",
        "DeleteGWSApplication",
        "GWSGetEventList",
        "StartGWSApplication",
        "CancelGWSApplication",
        "RestartGWSApplication",
    ],
    query_keys=["ProjectId"],
    **_FLINK,
)
_register(
    ["CreateGWSApplicationDraft", "UpdateGWSApplicationDraft"],
    query_keys=["ProjectId"],
    preserve_query_keys_in_body=["ProjectId"],
    **_FLINK,
)
_register(["DeployGWSApplicationDraft"], query_keys=["ProjectId", "Id"], **_FLINK)
_register(["ListGWSApplication"], query_keys=["PageSize", "PageNum", "SortField", "SortOrder"], **_FLINK)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def parse_json_value(raw: str | None) -> dict[str, Any]:
    if raw is None or raw == "":
        return {}
    if raw.startswith("@"):
        with open(raw[1:], "r", encoding="utf-8") as f:
            raw = f.read()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON for --params: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit("--params must be a JSON object")
    return value


def parse_key_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    keys = [part.strip() for part in raw.split(",")]
    return [key for key in keys if key]


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _env_value(env_getter, name: str) -> str:
    try:
        value = env_getter(name, "")
    except TypeError:
        value = env_getter(name)
    if value is None:
        return ""
    return str(value).strip()


def check_ve_login_status() -> str:
    try:
        completed = subprocess.run(
            ["ve", "sts", "GetCallerIdentity"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return "`ve` command not found."
    except subprocess.TimeoutExpired:
        return "`ve sts GetCallerIdentity` timed out."

    output = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part and part.strip())
    if completed.returncode == 0:
        return "`ve sts GetCallerIdentity` succeeded; current ve credentials are usable."
    return output or f"`ve sts GetCallerIdentity` failed with exit code {completed.returncode}."


# ---------------------------------------------------------------------------
# Credential resolution (env -> ve profile AK/SK -> ve console-login cache)
# ---------------------------------------------------------------------------
def _config_path(env_getter=env) -> str:
    return _env_value(env_getter, CLI_CONFIG_FILE_ENV) or os.path.expanduser("~/.volcengine/config.json")


def _load_cli_config(env_getter=env) -> tuple[dict[str, Any], str]:
    path = _config_path(env_getter)
    if not os.path.isfile(path):
        raise CredentialResolutionError(f"Volcengine CLI config file not found at {path}.")
    try:
        with open(path, "r", encoding="utf-8") as f:
            value = json.load(f)
    except OSError as exc:
        raise CredentialResolutionError(f"Failed to read Volcengine CLI config file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise CredentialResolutionError(f"Failed to parse Volcengine CLI config file {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CredentialResolutionError(f"Volcengine CLI config file {path} must contain a JSON object.")
    return value, path


def _select_profile_name(
    config: dict[str, Any],
    *,
    profile: str | None,
    env_getter=env,
) -> tuple[str, str]:
    explicit_profile = str(profile).strip() if profile else ""
    if explicit_profile:
        return explicit_profile, "--profile"
    current = config.get("current")
    if isinstance(current, str) and current.strip():
        return current.strip(), "current"
    env_profile = _env_value(env_getter, "VOLCENGINE_PROFILE")
    if env_profile:
        return env_profile, "VOLCENGINE_PROFILE"
    stack_profile = _env_value(env_getter, "VOLCSTACK_PROFILE")
    if stack_profile:
        return stack_profile, "VOLCSTACK_PROFILE"
    raise CredentialResolutionError(
        "No active Volcengine CLI profile is configured. Run `ve configure profile --profile <name>`, "
        "pass --profile after the user selects one, or set VOLCENGINE_ACCESS_KEY and VOLCENGINE_SECRET_KEY."
    )


def _get_profile(config: dict[str, Any], profile_name: str, profile_source: str) -> dict[str, Any]:
    profiles = config.get("profiles")
    if not isinstance(profiles, dict):
        raise CredentialResolutionError("Volcengine CLI config does not contain a valid profiles object.")
    profile = profiles.get(profile_name)
    if not isinstance(profile, dict):
        raise CredentialResolutionError(
            f"Volcengine CLI profile {profile_name!r} from {profile_source} was not found in config."
        )
    return profile


def _profile_value(profile: dict[str, Any], key: str) -> str:
    value = profile.get(key)
    return value.strip() if isinstance(value, str) else ""


def _login_cache_filename(login_session: str) -> str:
    return hashlib.sha1(login_session.encode("utf-8")).hexdigest() + ".json"


def _login_cache_dir(config_path: str, env_getter=env) -> str:
    custom = _env_value(env_getter, LOGIN_CACHE_DIRECTORY_ENV)
    if custom:
        return custom
    return os.path.join(os.path.dirname(config_path), "login", "cache")


def _parse_rfc3339(value: str) -> datetime.datetime:
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    parsed = datetime.datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


def _parse_console_login_access_token(access_token: Any, cache_path: str) -> tuple[str, str, str]:
    if isinstance(access_token, dict):
        creds = access_token
    elif isinstance(access_token, str):
        try:
            parsed = json.loads(access_token)
        except json.JSONDecodeError as exc:
            raise CredentialResolutionError(f"Failed to parse console-login access_token in {cache_path}: {exc}") from exc
        if not isinstance(parsed, dict):
            raise CredentialResolutionError(f"console-login access_token in {cache_path} is not a JSON object.")
        creds = parsed
    else:
        raise CredentialResolutionError(f"console-login token cache {cache_path} does not contain valid access_token.")

    ak = creds.get("access_key_id")
    sk = creds.get("secret_access_key")
    token = creds.get("session_token")
    ak = ak.strip() if isinstance(ak, str) else ""
    sk = sk.strip() if isinstance(sk, str) else ""
    token = token.strip() if isinstance(token, str) else ""
    if not ak or not sk or not token:
        raise CredentialResolutionError(f"console-login access_token in {cache_path} is missing STS credential fields.")
    return ak, sk, token


def _read_console_login_cache(
    *,
    profile_name: str,
    profile: dict[str, Any],
    config_path: str,
    env_getter=env,
) -> ResolvedCredentials:
    login_session = _profile_value(profile, "login-session")
    if not login_session:
        raise CredentialResolutionError(
            f"Volcengine CLI profile {profile_name!r} does not contain usable access-key/secret-key "
            "or login-session. Run `ve login` or `ve configure set` first."
        )
    cache_path = os.path.join(_login_cache_dir(config_path, env_getter), _login_cache_filename(login_session))
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            cache = json.load(f)
    except OSError as exc:
        raise CredentialResolutionError(
            f"Failed to read console-login cache for profile {profile_name!r} at {cache_path}: {exc}. "
            "Run `ve login` first."
        ) from exc
    except json.JSONDecodeError as exc:
        raise CredentialResolutionError(f"Failed to parse console-login cache {cache_path}: {exc}") from exc
    if not isinstance(cache, dict):
        raise CredentialResolutionError(f"console-login cache {cache_path} must contain a JSON object.")

    issued_at_raw = cache.get("issued_at")
    issued_at = issued_at_raw.strip() if isinstance(issued_at_raw, str) else ""
    try:
        expires_in = int(cache.get("expires_in", 0))
    except (TypeError, ValueError):
        expires_in = 0
    if not issued_at or expires_in <= 0:
        raise CredentialResolutionError(f"console-login cache {cache_path} is missing valid issued_at/expires_in.")
    try:
        expiration = _parse_rfc3339(issued_at) + datetime.timedelta(seconds=expires_in)
    except ValueError as exc:
        raise CredentialResolutionError(f"Failed to parse issued_at in console-login cache {cache_path}: {exc}") from exc
    if utc_now() >= expiration - datetime.timedelta(seconds=60):
        raise CredentialResolutionError(
            f"console-login cache for profile {profile_name!r} is expired. Run `ve login` to refresh it."
        )

    ak, sk, token = _parse_console_login_access_token(cache.get("access_token"), cache_path)
    return ResolvedCredentials(
        ak=ak,
        sk=sk,
        session_token=token,
        provider_name="VolcengineCLIConsoleLoginCache",
    )


def resolve_volcengine_credentials(
    *,
    profile: str | None = None,
    session_token: str | None = None,
    env_getter=env,
    notify=None,
) -> ResolvedCredentials:
    """Resolve AK/SK from env first, then from existing Volcengine CLI credentials."""
    env_ak = _env_value(env_getter, "VOLCENGINE_ACCESS_KEY")
    env_sk = _env_value(env_getter, "VOLCENGINE_SECRET_KEY")
    if env_ak and env_sk:
        return ResolvedCredentials(
            ak=env_ak,
            sk=env_sk,
            session_token=(
                str(session_token).strip()
                if session_token is not None
                else _env_value(env_getter, "VOLCENGINE_SESSION_TOKEN")
            ),
            provider_name="EnvironmentVariableCredentialProvider",
        )

    if notify:
        missing = []
        if not env_ak:
            missing.append("VOLCENGINE_ACCESS_KEY")
        if not env_sk:
            missing.append("VOLCENGINE_SECRET_KEY")
        notify(
            "{} not detected; checking `ve sts GetCallerIdentity` before reading existing ve profile/login-cache credentials.".format(
                " and ".join(missing)
            )
        )
        ve_status = check_ve_login_status()
        notify(f"ve credential check: {ve_status}")

    try:
        config, resolved_config_path = _load_cli_config(env_getter)
        profile_name, profile_source = _select_profile_name(config, profile=profile, env_getter=env_getter)
        selected_profile = _get_profile(config, profile_name, profile_source)

        ak = _profile_value(selected_profile, "access-key")
        sk = _profile_value(selected_profile, "secret-key")
        if ak and sk:
            return ResolvedCredentials(
                ak=ak,
                sk=sk,
                session_token=(
                    str(session_token).strip()
                    if session_token is not None
                    else _profile_value(selected_profile, "session-token")
                ),
                provider_name=f"VolcengineCLIProfile({profile_name})",
            )

        resolved = _read_console_login_cache(
            profile_name=profile_name,
            profile=selected_profile,
            config_path=resolved_config_path,
            env_getter=env_getter,
        )
    except CredentialResolutionError as exc:
        raise CredentialResolutionError(
            f"{exc} Run `ve login` or set VOLCENGINE_ACCESS_KEY and VOLCENGINE_SECRET_KEY environment variables."
        ) from exc

    if session_token is not None:
        return ResolvedCredentials(
            ak=resolved.ak,
            sk=resolved.sk,
            session_token=str(session_token).strip(),
            provider_name=resolved.provider_name,
        )
    return resolved


# ---------------------------------------------------------------------------
# Request shaping and HMAC-SHA256 signing
# ---------------------------------------------------------------------------
def split_query_body(
    params: dict[str, Any],
    query_keys: list[str] | None,
    preserve_query_keys_in_body: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not query_keys:
        return {}, params
    preserve_query_keys_in_body = preserve_query_keys_in_body or []
    query: dict[str, Any] = {}
    body: dict[str, Any] = {}
    for key, value in params.items():
        if key in query_keys:
            query[key] = value
        if key not in query_keys or key in preserve_query_keys_in_body:
            body[key] = value
    return query, body


def norm_query(params: dict[str, Any]) -> str:
    query = ""
    for key in sorted(params.keys()):
        value = params[key]
        if isinstance(value, list):
            for item in value:
                query += quote(key, safe="-_.~") + "=" + quote(str(item), safe="-_.~") + "&"
        else:
            query += quote(key, safe="-_.~") + "=" + quote(str(value), safe="-_.~") + "&"
    return query[:-1].replace("+", "%20")


def hmac_sha256(key: bytes, content: str) -> bytes:
    return hmac.new(key, content.encode("utf-8"), hashlib.sha256).digest()


def hash_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def encode_body(body: dict[str, Any], content_type: str) -> str:
    if content_type == FORM_CONTENT_TYPE:
        return urlencode(body, doseq=True)
    return json.dumps(body)


def build_signed_request(
    *,
    ak: str,
    sk: str,
    session_token: str,
    region: str,
    host: str,
    service: str,
    version: str,
    action: str,
    method: str,
    content_type: str,
    query: dict[str, Any],
    body: dict[str, Any],
    scheme: str = "https",
    now: datetime.datetime | None = None,
) -> urllib_request.Request:
    """Build a signed urllib Request. GET folds the body into the query string."""
    method = method.upper()
    if method == "GET":
        request_query = {"Action": action, "Version": version, **body, **query}
        body_str = ""
    else:
        request_query = {"Action": action, "Version": version, **query}
        body_str = encode_body(body, content_type)

    x_date = (now or utc_now()).strftime("%Y%m%dT%H%M%SZ")
    short_x_date = x_date[:8]
    x_content_sha256 = hash_sha256(body_str)
    signed_headers = "content-type;host;x-content-sha256;x-date"
    canonical_request = "\n".join(
        [
            method,
            "/",
            norm_query(request_query),
            "\n".join(
                [
                    "content-type:" + content_type,
                    "host:" + host,
                    "x-content-sha256:" + x_content_sha256,
                    "x-date:" + x_date,
                ]
            ),
            "",
            signed_headers,
            x_content_sha256,
        ]
    )
    credential_scope = "/".join([short_x_date, region, service, "request"])
    string_to_sign = "\n".join(["HMAC-SHA256", x_date, credential_scope, hash_sha256(canonical_request)])
    k_date = hmac_sha256(sk.encode("utf-8"), short_x_date)
    k_region = hmac_sha256(k_date, region)
    k_service = hmac_sha256(k_region, service)
    k_signing = hmac_sha256(k_service, "request")
    signature = hmac_sha256(k_signing, string_to_sign).hex()
    headers = {
        "Host": host,
        "X-Content-Sha256": x_content_sha256,
        "X-Date": x_date,
        "Content-Type": content_type,
        "Authorization": (
            "HMAC-SHA256 Credential="
            + ak
            + "/"
            + credential_scope
            + ", SignedHeaders="
            + signed_headers
            + ", Signature="
            + signature
        ),
    }
    if session_token:
        headers["x-security-token"] = session_token

    url = f"{scheme}://{host}/?{norm_query(request_query)}"
    data = None if method == "GET" else body_str.encode("utf-8")
    return urllib_request.Request(url=url, data=data, headers=headers, method=method)


def send_request(req: urllib_request.Request, timeout: int = 30) -> tuple[Any, int, dict[str, str]]:
    try:
        with urllib_request.urlopen(req, timeout=timeout) as response:
            status_code = response.status
            response_headers = dict(response.headers.items())
            response_text = response.read().decode("utf-8")
    except urllib_error.HTTPError as exc:
        status_code = exc.code
        response_headers = dict(exc.headers.items())
        response_text = exc.read().decode("utf-8")

    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError:
        payload = response_text
    return payload, status_code, response_headers


def response_failed(payload: Any, status_code: int) -> bool:
    """True for HTTP failures and for Volcengine errors carried inside an HTTP 200."""
    if status_code >= 400:
        return True
    if not isinstance(payload, dict):
        return False
    metadata = payload.get("ResponseMetadata")
    return isinstance(metadata, dict) and metadata.get("Error") is not None


# ---------------------------------------------------------------------------
# Registry lookup / free mode
# ---------------------------------------------------------------------------
def registry_by_name() -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for entry in API_REGISTRY:
        index.setdefault(entry["name"], []).append(entry)
    return index


def find_registry_entry(api_name: str, service: str | None) -> dict[str, Any] | None:
    matches = registry_by_name().get(api_name, [])
    if service:
        matches = [entry for entry in matches if entry["service"] == service]
    if not matches:
        return None
    if len(matches) > 1:
        services = ", ".join(sorted({entry["service"] for entry in matches}))
        raise SystemExit(f"APIName {api_name} is ambiguous across services: {services}. Pass --service.")
    return matches[0]


def resolve_api(api_name: str, service: str | None) -> dict[str, Any]:
    entry = find_registry_entry(api_name, service)
    if entry is None:
        raise SystemExit(
            f"Unknown APIName: {api_name}. Use --list to see the registered query+body APIs, "
            "or pass --service/--version/--query-keys for free mode. For ordinary APIs use "
            f"`ve <service> {api_name} --version <ver> --endpoint <host> --force` instead."
        )
    return entry


def build_free_entry(args: argparse.Namespace) -> dict[str, Any]:
    missing = [flag for flag, value in (("--service", args.service), ("--version", args.version)) if not value]
    if missing:
        raise SystemExit(
            f"{args.api_name} is not in the registry; free mode needs {' and '.join(missing)} "
            "(plus --query-keys for the keys that belong in the URL)."
        )
    query_keys = parse_key_list(args.query_keys)
    if not query_keys:
        raise SystemExit(
            f"{args.api_name} is not in the registry and no --query-keys were given. An API without a "
            f"query/body split does not need this helper: use `ve {args.service} {args.api_name} "
            f"--version {args.version} --endpoint <host> --force`."
        )
    preserve = parse_key_list(args.body_keys_also)
    unknown_preserve = [key for key in preserve if key not in query_keys]
    if unknown_preserve:
        raise SystemExit(f"--body-keys-also lists keys that are not in --query-keys: {', '.join(unknown_preserve)}")
    entry: dict[str, Any] = {
        "name": args.api_name,
        "service": args.service,
        "version": args.version,
        "method": (args.method or "POST").upper(),
        "content_type": args.content_type or JSON_CONTENT_TYPE,
        "query_keys": query_keys,
        "summary": "Free-mode call (not in registry).",
        "free_mode": True,
    }
    if preserve:
        entry["preserve_query_keys_in_body"] = preserve
    return entry


def resolve_entry(args: argparse.Namespace) -> dict[str, Any]:
    entry = find_registry_entry(args.api_name, args.service)
    if entry is not None:
        if args.query_keys:
            raise SystemExit(
                f"{entry['name']} is a registered API; its query keys are fixed to "
                f"{', '.join(entry['query_keys'])}. Drop --query-keys."
            )
        return entry
    return build_free_entry(args)


def resolve_host(entry: dict[str, Any], region: str, explicit_host: str | None) -> str:
    if explicit_host:
        return explicit_host
    if entry.get("host_template"):
        return entry["host_template"].format(region=region)
    if entry.get("host"):
        return entry["host"]
    return env("VOLCENGINE_ENDPOINT") or DEFAULT_HOST


def print_list() -> None:
    for entry in sorted(API_REGISTRY, key=lambda e: (e["service"], e["name"])):
        print(
            f"{entry['name']}\t{entry['service']}\t{entry['version']}\t"
            f"{entry['method']}\tquery={','.join(entry['query_keys'])}\t{entry.get('summary', '')}"
        )


def print_describe(entry: dict[str, Any]) -> None:
    print(json.dumps(entry, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def prepare_request_shape(entry: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    """Everything needed to sign, minus credentials. Split out so it is testable offline."""
    expected_method = entry["method"].upper()
    if args.method and args.method.upper() != expected_method and not entry.get("free_mode"):
        raise SystemExit(f"{entry['name']} uses method {expected_method}, not {args.method.upper()}")
    method = (args.method or expected_method).upper()

    params = parse_json_value(args.params)
    query_params, body_params = split_query_body(params, entry.get("query_keys"), entry.get("preserve_query_keys_in_body"))
    region = args.region or env("VOLCENGINE_REGION") or DEFAULT_REGION
    host = resolve_host(entry, region, args.host)
    scheme = args.scheme or entry.get("scheme") or "https"
    if scheme != "https":
        raise SystemExit("Only HTTPS endpoints are supported by this helper.")
    content_type = args.content_type or entry.get("content_type") or JSON_CONTENT_TYPE
    return {
        "region": region,
        "host": host,
        "service": entry["service"],
        "version": entry["version"],
        "action": entry["name"],
        "method": method,
        "content_type": content_type,
        "query": query_params,
        "body": body_params,
        "scheme": scheme,
    }


def call_api(args: argparse.Namespace) -> int:
    entry = resolve_entry(args)
    shape = prepare_request_shape(entry, args)

    try:
        credentials = resolve_volcengine_credentials(
            profile=args.profile,
            session_token=args.session_token,
            notify=lambda message: print(message, file=sys.stderr),
        )
    except CredentialResolutionError as exc:
        raise SystemExit(str(exc)) from exc

    req = build_signed_request(
        ak=credentials.ak,
        sk=credentials.sk,
        session_token=credentials.session_token,
        **shape,
    )
    response, status_code, response_headers = send_request(req)

    if args.output == "json":
        print(json.dumps(response, ensure_ascii=False))
    else:
        print(f"Status Code: {status_code}")
        print(json.dumps(response, ensure_ascii=False, indent=2))
        if args.show_headers:
            print("Response Headers:")
            print(json.dumps(dict(response_headers), ensure_ascii=False, indent=2, default=str))
    return 1 if response_failed(response, status_code) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Call Volcengine APIs that need URL query parameters and a request body in one POST. "
        "For everything else use `ve <service> <Action> --version <ver> --endpoint <host> --force`.",
    )
    parser.add_argument("--api", "--api-name", dest="api_name", help="Action name to call")
    parser.add_argument("--params", "--param", default="{}", help="JSON object or @file.json, default {}")
    parser.add_argument("--service", help="ServiceCode (required in free mode; disambiguates registry names)")
    parser.add_argument("--version", help="API version, e.g. 2021-06-01 (free mode only)")
    parser.add_argument(
        "--query-keys",
        help="Comma-separated param keys sent in the URL query string instead of the body (free mode only)",
    )
    parser.add_argument(
        "--body-keys-also",
        help="Comma-separated subset of --query-keys that must ALSO stay in the body (free mode only)",
    )
    parser.add_argument("--method", choices=["GET", "POST", "get", "post"], help="HTTP method; registry entries are fixed to POST")
    parser.add_argument("--region", help="Request region, default VOLCENGINE_REGION or cn-beijing")
    parser.add_argument("--host", help="Override endpoint host; otherwise registry host/template or VOLCENGINE_ENDPOINT or open.volcengineapi.com")
    parser.add_argument("--scheme", choices=["https"], help="HTTPS only")
    parser.add_argument("--content-type", help="Override content type (application/json or application/x-www-form-urlencoded)")
    parser.add_argument("--session-token", help="Override VOLCENGINE_SESSION_TOKEN")
    parser.add_argument("--profile", help="Volcengine CLI profile name for ve login/config credentials")
    parser.add_argument("--output", choices=["pretty", "json"], default="pretty")
    parser.add_argument("--show-headers", action="store_true")
    parser.add_argument("--list", action="store_true", help="List registered query+body APIs")
    parser.add_argument("--describe", metavar="APIName", help="Print registry metadata for an API")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.list:
        print_list()
        return 0
    if args.describe:
        print_describe(resolve_api(args.describe, args.service))
        return 0
    if not args.api_name:
        parser.error("--api is required unless --list or --describe is used")
    return call_api(args)


if __name__ == "__main__":
    raise SystemExit(main())
