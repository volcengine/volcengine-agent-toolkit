#!/usr/bin/env python3
import argparse
import datetime
import hashlib
import hmac
import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

SERVICE = "tos"
VERSION = "2018-01-01"
CONTENT_TYPE = "application/x-www-form-urlencoded"
SUPPORTED_REGION = "cn-beijing"
KNOWN_HOSTS = {
    "cn-beijing": "tos.cn-beijing.volcengineapi.com",
}
RETRYABLE_FINAL_STATES = {"NonActivated"}
BLOCKING_FINAL_STATES = {"Stopping", "Closed", "Terminate"}
DEFAULT_MAX_POLLS = 8
DEFAULT_POLL_INTERVAL_SECONDS = 3


class TosActivationError(Exception):
    def __init__(self, message, *, details=None, exit_code=1):
        super().__init__(message)
        self.details = details
        self.exit_code = exit_code


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def normalize_query(params):
    items = []
    for key in sorted(params.keys()):
        value = params[key]
        if isinstance(value, list):
            for entry in value:
                items.append(
                    f"{quote(str(key), safe='-_.~')}={quote(str(entry), safe='-_.~')}"
                )
        else:
            items.append(
                f"{quote(str(key), safe='-_.~')}={quote(str(value), safe='-_.~')}"
            )
    return "&".join(items)


def hash_sha256(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def hmac_sha256(key, content):
    return hmac.new(key, content.encode("utf-8"), hashlib.sha256).digest()


def resolve_host(region):
    if region not in KNOWN_HOSTS:
        raise TosActivationError(
            f"Unsupported TOS OpenAPI region: {region!r}",
            details={
                "supported_regions": sorted(KNOWN_HOSTS.keys()),
            },
            exit_code=4,
        )
    return KNOWN_HOSTS[region]


def build_signed_headers(region, credentials, query):
    host = resolve_host(region)
    method = "POST"
    body = ""
    request_time = utc_now()
    x_date = request_time.strftime("%Y%m%dT%H%M%SZ")
    short_x_date = x_date[:8]
    body_hash = hash_sha256(body)

    canonical_header_items = [
        ("host", host),
        ("x-date", x_date),
    ]
    if credentials.get("session_token"):
        canonical_header_items.append(("x-security-token", credentials["session_token"]))

    signed_headers = ";".join(name for name, _ in canonical_header_items)
    canonical_headers = "\n".join(f"{name}:{value}" for name, value in canonical_header_items)

    canonical_request = "\n".join(
        [
            method.upper(),
            "/",
            normalize_query(query),
            canonical_headers,
            "",
            signed_headers,
            body_hash,
        ]
    )
    hashed_canonical_request = hash_sha256(canonical_request)
    credential_scope = "/".join([short_x_date, region, SERVICE, "request"])
    string_to_sign = "\n".join(
        ["HMAC-SHA256", x_date, credential_scope, hashed_canonical_request]
    )

    k_date = hmac_sha256(credentials["secret_key"].encode("utf-8"), short_x_date)
    k_region = hmac_sha256(k_date, region)
    k_service = hmac_sha256(k_region, SERVICE)
    k_signing = hmac_sha256(k_service, "request")
    signature = hmac_sha256(k_signing, string_to_sign).hex()

    headers = {
        "Host": host,
        "X-Date": x_date,
        "Authorization": (
            "HMAC-SHA256 Credential={}/{}, SignedHeaders={}, Signature={}".format(
                credentials["access_key"],
                credential_scope,
                signed_headers,
                signature,
            )
        ),
    }
    if credentials.get("session_token"):
        headers["X-Security-Token"] = credentials["session_token"]

    return headers


def load_json_response(response):
    payload = response.read().decode("utf-8")
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise TosActivationError(
            "TOS OpenAPI returned a non-JSON response",
            details={"payload": payload},
            exit_code=1,
        ) from exc


def invoke_openapi(action, args):
    host = resolve_host(args.region)
    query = {
        "Action": action,
        "Version": VERSION,
        "ServiceName": SERVICE,
    }
    body = ""
    credentials = {
        "access_key": args.access_key,
        "secret_key": args.secret_key,
        "session_token": args.session_token,
    }
    headers = build_signed_headers(args.region, credentials, query)
    url = f"https://{host}/?{normalize_query(query)}"
    request = Request(url=url, headers=headers, method="POST", data=body.encode("utf-8"))

    try:
        with urlopen(request, timeout=args.timeout_seconds) as response:
            payload = load_json_response(response)
            response_error = payload.get("ResponseMetadata", {}).get("Error")
            if response_error:
                raise TosActivationError(
                    f"TOS OpenAPI {action} returned an API error",
                    details=payload,
                    exit_code=1,
                )
            return payload
    except HTTPError as exc:
        details = None
        try:
            details = load_json_response(exc)
        except TosActivationError:
            payload = exc.read().decode("utf-8", errors="replace")
            details = {"payload": payload}
        raise TosActivationError(
            f"TOS OpenAPI {action} failed with HTTP {exc.code}",
            details=details,
            exit_code=1,
        ) from exc
    except URLError as exc:
        raise TosActivationError(
            f"TOS OpenAPI {action} request failed: {exc}",
            exit_code=1,
        ) from exc


def extract_request_id(response):
    return response.get("ResponseMetadata", {}).get("RequestId")


def extract_status(response):
    return response.get("Result", {}).get("Status")


def poll_account_status(args):
    last_response = None
    for attempt in range(1, args.max_polls + 1):
        last_response = invoke_openapi("GetAccountStatus", args)
        status = extract_status(last_response)
        if status == "Activated":
            return last_response, attempt
        if status in BLOCKING_FINAL_STATES:
            raise TosActivationError(
                f"TOS account status became {status} while waiting for activation",
                details={
                    "final_status": status,
                    "verify_request_id": extract_request_id(last_response),
                    "region": args.region,
                    "host": resolve_host(args.region),
                    "attempt": attempt,
                },
                exit_code=5,
            )
        if attempt < args.max_polls:
            time.sleep(args.poll_interval_seconds)

    return last_response, args.max_polls


def ensure_tos_activated(args):
    initial_response = invoke_openapi("GetAccountStatus", args)
    initial_status = extract_status(initial_response)

    if initial_status == "Activated":
        return {
            "changed": False,
            "initial_status": initial_status,
            "final_status": initial_status,
            "status_request_id": extract_request_id(initial_response),
            "region": args.region,
            "host": resolve_host(args.region),
        }

    if initial_status in BLOCKING_FINAL_STATES:
        raise TosActivationError(
            f"TOS account status is {initial_status} and cannot be auto-activated",
            details={
                "initial_status": initial_status,
                "status_request_id": extract_request_id(initial_response),
                "region": args.region,
                "host": resolve_host(args.region),
            },
            exit_code=5,
        )

    if initial_status not in RETRYABLE_FINAL_STATES:
        raise TosActivationError(
            f"Unexpected TOS account status: {initial_status!r}",
            details={
                "initial_status": initial_status,
                "status_request_id": extract_request_id(initial_response),
                "region": args.region,
                "host": resolve_host(args.region),
            },
            exit_code=1,
        )

    activate_response = invoke_openapi("ActiveTosSvc", args)
    verify_response, verify_attempts = poll_account_status(args)
    final_status = extract_status(verify_response)

    if final_status != "Activated":
        raise TosActivationError(
            "TOS activation verification failed",
            details={
                "initial_status": initial_status,
                "final_status": final_status,
                "activate_request_id": extract_request_id(activate_response),
                "verify_request_id": extract_request_id(verify_response),
                "region": args.region,
                "host": resolve_host(args.region),
                "verify_attempts": verify_attempts,
            },
            exit_code=5,
        )

    return {
        "changed": True,
        "initial_status": initial_status,
        "final_status": final_status,
        "activate_request_id": extract_request_id(activate_response),
        "verify_request_id": extract_request_id(verify_response),
        "region": args.region,
        "host": resolve_host(args.region),
        "verify_attempts": verify_attempts,
    }


def parse_args():
    parser = argparse.ArgumentParser(
        description="Ensure the current account has TOS activated via Volcengine OpenAPI."
    )
    parser.add_argument("--region", required=True, help="Volcengine region for the TOS control plane.")
    parser.add_argument("--access-key", required=True, help="Access key used for signing.")
    parser.add_argument("--secret-key", required=True, help="Secret key used for signing.")
    parser.add_argument("--session-token", help="Optional STS session token.")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=30,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--max-polls",
        type=int,
        default=DEFAULT_MAX_POLLS,
        help="Maximum number of verification polls after activation.",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=int,
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        help="Seconds to wait between verification polls.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        result = ensure_tos_activated(args)
    except TosActivationError as exc:
        payload = {
            "error": str(exc),
            "details": exc.details,
        }
        print(json.dumps(payload, ensure_ascii=True), file=sys.stderr)
        return exc.exit_code

    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
