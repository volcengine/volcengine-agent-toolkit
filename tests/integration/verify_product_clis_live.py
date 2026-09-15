#!/usr/bin/env python3
"""Opt-in, authenticated cloud checks for ve tosutil and ve arkcli.

Run directly; this file is intentionally outside default unittest discovery.
Credentials stay in the tools' own configuration. Reports contain assertions,
counts and public model metadata, never raw responses or account/resource IDs.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from typing import Any, Callable


class LiveChecks:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.results: list[dict[str, Any]] = []
        self.account_id = ""
        self.model_name = ""
        self.model_version = ""

    def step(
        self,
        case_id: str,
        command: list[str],
        template: str,
        check: Callable[[str], dict[str, Any]],
    ) -> bool:
        started = time.monotonic()
        row: dict[str, Any] = {"case": case_id, "command": template}
        env = os.environ.copy()
        env["VOLCENGINE_CLI_DISABLE_UPDATE_CHECK"] = "1"
        env.update(
            VE_CALLER_TYPE="ai_agent",
            VE_CALLER_NAME=self.args.agent_id,
            VE_SKILL_NAME=self.args.skill_name,
        )
        if command and command[0] == "arkcli":
            for name in (
                "ARKCLI_NO_UPDATE_NOTIFIER",
                "ARKCLI_CALLER_TYPE",
                "ARKCLI_CALLER_NAME",
                "ARKCLI_SKILL_NAME",
            ):
                env.pop(name, None)
        try:
            completed = subprocess.run(
                [self.args.ve, *command],
                env=env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=self.args.timeout,
                check=False,
            )
            row["exit_code"] = completed.returncode
            if completed.returncode:
                raise AssertionError("CLI returned a nonzero exit code; raw output withheld")
            row["evidence"] = check(completed.stdout)
            row["status"] = "PASS"
        except AssertionError as error:
            row.update(status="FAIL", reason=str(error))
        except subprocess.TimeoutExpired:
            row.update(status="FAIL", reason="command timed out")
        except (OSError, ValueError, TypeError, KeyError):
            row.update(status="FAIL", reason="execution or response schema validation failed")
        row["duration_ms"] = round((time.monotonic() - started) * 1000)
        self.results.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        return row["status"] == "PASS"

    def identity(self, stdout: str) -> dict[str, Any]:
        payload = json.loads(stdout)
        assert not payload.get("ResponseMetadata", {}).get("Error"), "STS returned an API error"
        result = payload["Result"]
        account = result.get("AccountId")
        assert account and result.get("IdentityType"), "STS identity fields are missing"
        self.account_id = str(account)
        return {"authenticated": True, "identity_type": result["IdentityType"]}

    def bucket_list(self, stdout: str) -> dict[str, Any]:
        match = re.search(r"Bucket number is:\s*(\d+)", stdout)
        assert match, "TOS did not return a bucket listing summary"
        buckets = re.findall(r"tos://([^\s/]+)", stdout)
        assert self.args.tos_bucket in buckets, "selected bucket was not present in the listing"
        count = int(match.group(1))
        assert count == len(buckets), "TOS listing count does not match the returned rows"
        return {"returned_bucket_count": count, "selected_bucket_present": True}

    def bucket_stat(self, stdout: str) -> dict[str, Any]:
        assert re.search(
            r"(?m)^\s*tos://" + re.escape(self.args.tos_bucket) + r"\s*$", stdout
        ), "TOS stat returned a different bucket"
        region = re.search(r"Region:\s*\n\s*(\S+)", stdout)
        storage = re.search(r"StorageClass:\s*\n\s*(\S+)", stdout)
        assert region and region.group(1) == self.args.tos_region, "bucket region did not match"
        assert storage, "TOS stat did not return a storage class"
        return {"bucket_matches": True, "region_matches": True, "storage_class_present": True}

    def ark_auth(self, stdout: str) -> dict[str, Any]:
        payload = json.loads(stdout)
        assert payload.get("logged_in") is True, "Ark CLI is not authenticated"
        account = payload.get("account_id")
        assert account and str(account) == self.account_id, "Ark and ve accounts do not match"
        return {"authenticated": True, "same_account_as_ve": True}

    def model_search(self, stdout: str) -> dict[str, Any]:
        payload = json.loads(stdout)
        assert not payload.get("error"), "Ark model search returned an error"
        items = payload.get("items")
        assert isinstance(items, list) and 0 < len(items) <= 3, "expected one to three models"
        self.model_name = items[0]["name"]
        self.model_version = items[0].get("primary_version") or ""
        assert isinstance(self.model_name, str) and self.model_name, "model name is missing"
        assert isinstance(self.model_version, str), "model version must be a string"
        return {"returned_model_count": len(items), "model_id_taken_from_live_response": True}

    def model_get(self, stdout: str) -> dict[str, Any]:
        payload = json.loads(stdout)
        assert not payload.get("error"), "Ark model get returned an error"
        assert payload.get("name") == self.model_name, "model detail did not match the search result"
        assert payload.get("primary_version") == self.model_version, "model version did not match"
        return {"name_matches_search": True, "version_matches_search": True}

    def run(self) -> bool:
        if not self.step("VE-AUTH", ["sts", "GetCallerIdentity"], "ve sts GetCallerIdentity", self.identity):
            return False

        config = "-conf=" + str(self.args.tos_config)
        if self.step("TOS-LIST", ["tosutil", "ls", config], "ve tosutil ls -conf=<config>", self.bucket_list):
            self.step(
                "TOS-STAT",
                ["tosutil", "stat", "tos://" + self.args.tos_bucket, config],
                "ve tosutil stat tos://<bucket> -conf=<config>",
                self.bucket_stat,
            )

        ark_flags = ["--profile", self.args.ark_profile] if self.args.ark_profile else []
        if self.step(
            "ARK-AUTH",
            ["arkcli", "auth", "whoami", "--format", "json", *ark_flags],
            "ve arkcli auth whoami --format json [--profile <profile>]",
            self.ark_auth,
        ) and self.step(
            "ARK-SEARCH",
            ["arkcli", "models", "search", self.args.keyword, "--size", "3", "--refresh-cache", "--format", "json", *ark_flags],
            "ve arkcli models search <keyword> --size 3 --refresh-cache --format json [--profile <profile>]",
            self.model_search,
        ):
            model = self.model_name + ("-" + self.model_version if self.model_version else "")
            self.step(
                "ARK-GET",
                ["arkcli", "models", "get", model, "--format", "json", *ark_flags],
                "ve arkcli models get <live-model-id> --format json [--profile <profile>]",
                self.model_get,
            )
        return len(self.results) == 6 and all(row["status"] == "PASS" for row in self.results)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ve", default="ve", help="newly built ve executable")
    parser.add_argument("--agent-id", required=True, help="actual Agent host identifier for this execution")
    parser.add_argument("--skill-name", required=True, help="active Volcengine skill name for this execution")
    parser.add_argument("--tos-config", type=Path, required=True, help="existing authenticated tosutil config")
    parser.add_argument("--tos-bucket", required=True, help="existing bucket, without tos://")
    parser.add_argument("--tos-region", required=True, help="expected bucket region; does not change profiles")
    parser.add_argument("--ark-profile", help="explicit existing Ark profile; defaults to current Ark context")
    parser.add_argument("--keyword", default="doubao", help="public model search keyword")
    parser.add_argument("--timeout", type=int, default=60, help="per-command deadline in seconds")
    parser.add_argument("--report", type=Path, required=True, help="sanitized JSON report path")
    args = parser.parse_args()
    args.agent_id = args.agent_id.strip()
    if not args.agent_id:
        parser.error("--agent-id must identify the actual Agent host")
    if not re.fullmatch(r"volcengine-[a-z0-9]+(?:-[a-z0-9]+)*", args.skill_name):
        parser.error("--skill-name must be the active volcengine-* skill name")
    args.tos_config = args.tos_config.expanduser().resolve()
    if not args.tos_config.is_file():
        parser.error("--tos-config must be an existing file")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", args.tos_bucket):
        parser.error("--tos-bucket must be a bucket name, not a URI or object path")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    resolved = shutil.which(args.ve)
    if not resolved:
        parser.error("ve executable was not found")
    args.ve = resolved
    suite = LiveChecks(args)
    passed = suite.run()
    report = {
        "suite": "ve-product-clis-authenticated-readonly",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "expected_cases": 6,
        "results": suite.results,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
