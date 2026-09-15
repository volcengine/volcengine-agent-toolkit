"""Tests for skills/core/volcengine-cli/scripts/ve_login_remote.sh (device-code flow).

A fake `ve` placed ahead in PATH plays the CLI: it prints the device-code
block, waits for an "approval" marker file, then reports success. The helper
keeps its state under /tmp/ve_login_<uid>.*, so the suite refuses to run while
a real login is in progress and always aborts its own session afterwards.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "skills" / "core" / "volcengine-cli" / "scripts" / "ve_login_remote.sh"
BASH = shutil.which("bash") or "bash"

FAKE_VE = r'''#!/bin/sh
# Fake ve for tests. Behaviour is selected by FAKE_VE_MODE.
if [ -n "${FAKE_VE_CALLER_LOG:-}" ]; then
  printf '%s|%s|%s|%s\n' "${1-} ${2-}" "${VE_CALLER_TYPE-}" "${VE_CALLER_NAME-}" "${VE_SKILL_NAME-}" >> "$FAKE_VE_CALLER_LOG"
fi
case "$1 $2" in
  "login --help")
    if [ "${FAKE_VE_MODE:-device}" = "old" ]; then
      echo "Usage: ve login [flags]"; echo "  --remote   legacy"
    else
      echo "Usage: ve login [flags]"; echo "  --no-browser   Do not automatically open the browser during login"
    fi
    exit 0 ;;
  "login --no-browser")
    printf '%s\n' "$@" > "$FAKE_VE_LOGIN_ARGS"
    # Real ve follows the system locale unless --lang is given: on zh_CN it
    # prints Chinese. Mirror that so the helper must pin the language itself.
    english=0
    for arg in "$@"; do
      if [ "$prev" = "--lang" ] && { [ "$arg" = "en" ] || [ "$arg" = "EN" ]; }; then english=1; fi
      prev="$arg"
    done
    if [ "$english" = "1" ]; then
      echo "Browser will not be automatically opened."
      echo "Open the following URL to authorize this device:"
      echo ""
      echo "https://signin.volcengine.com/authorize/oauth/device?trace_id=trace-1"
      echo ""
      echo "Then enter the code:"
      echo ""
      echo "ABCD-1234"
      echo "Alternatively, open the following URL to prefill the code:"
      echo "https://signin.volcengine.com/authorize/oauth/device?trace_id=trace-1&user_code=ABCD-1234"
      echo "This device code expires in 300 seconds."
    else
      echo "浏览器不会自动打开。"
      echo "请打开以下地址授权此设备："
      echo ""
      echo "https://signin.volcengine.com/authorize/oauth/device?trace_id=trace-1"
      echo ""
      echo "然后输入以下用户码："
      echo ""
      echo "ABCD-1234"
      echo "此设备码将在 300 秒后过期。"
    fi
    while [ ! -f "$FAKE_VE_APPROVE" ]; do sleep 0.2; done
    if [ "$(cat "$FAKE_VE_APPROVE")" = "deny" ]; then
      echo "device authorization was denied"; exit 1
    fi
    echo "Successfully logged in!"
    exit 0 ;;
  "sts GetCallerIdentity")
    printf '%s\n' "$@" > "$FAKE_VE_STS_ARGS"
    if [ "${FAKE_VE_STS_FAIL:-0}" = "1" ]; then
      echo "RequestError: send request failed"; exit 1
    fi
    echo '{"ResponseMetadata":{},"Result":{"AccountId":"<account-id>"}}'
    exit 0 ;;
  *)
    echo "fake ve: unexpected args: $*" >&2; exit 99 ;;
esac
'''


class VeLoginRemoteTest(unittest.TestCase):
    def setUp(self) -> None:
        probe = subprocess.run([BASH, str(SCRIPT), "status"], capture_output=True, text=True)
        if probe.returncode == 0:
            self.skipTest("a real ve login session is alive for this user; not touching it")
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        fake = self.bin / "ve"
        fake.write_text(FAKE_VE, encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        self.approve = self.root / "approve"
        self.login_args = self.root / "login_args"
        self.sts_args = self.root / "sts_args"
        self.env = {
            **os.environ,
            "PATH": f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "FAKE_VE_APPROVE": str(self.approve),
            "FAKE_VE_LOGIN_ARGS": str(self.login_args),
            "FAKE_VE_STS_ARGS": str(self.sts_args),
            "VE_LOGIN_URL_TIMEOUT": "10",
        }

    def tearDown(self) -> None:
        subprocess.run([BASH, str(SCRIPT), "abort"], capture_output=True, text=True, env=self.env)
        self._tmp.cleanup()

    def run_helper(self, *args: str, env_extra: dict[str, str] | None = None, timeout: int = 30):
        env = dict(self.env)
        if env_extra:
            env.update(env_extra)
        return subprocess.run([BASH, str(SCRIPT), *args], capture_output=True, text=True, env=env, timeout=timeout)

    @staticmethod
    def kv(text: str) -> dict[str, str]:
        out = {}
        for line in text.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                out[k] = v
        return out

    def wait_for_exit(self, code: int, *args: str, attempts: int = 20):
        for _ in range(attempts):
            result = self.run_helper(*args)
            if result.returncode == code:
                return result
            time.sleep(0.25)
        return result

    def test_caller_metadata_reaches_detached_login_and_later_verification(self) -> None:
        cases = [
            ("codex", "volcengine-cli"),
            ("claude-code", "volcengine-troubleshooting"),
            ("opencode", "volcengine-knowledge-search"),
        ]
        for index, (agent, skill) in enumerate(cases):
            with self.subTest(agent=agent, skill=skill):
                caller_log = self.root / f"caller_metadata_{index}"
                metadata = {
                    "VE_CALLER_TYPE": "ai_agent",
                    "VE_CALLER_NAME": agent,
                    "VE_SKILL_NAME": skill,
                }
                self.env.update(metadata)
                self.env["FAKE_VE_CALLER_LOG"] = str(caller_log)
                self.approve.unlink(missing_ok=True)
                try:
                    started = self.run_helper("start", "cn-beijing")
                    self.assertEqual(started.returncode, 0, started.stderr)
                    self.approve.touch()
                    verified = self.wait_for_exit(0, "verify")
                    self.assertEqual(verified.returncode, 0, verified.stderr)

                    calls = [line.split("|") for line in caller_log.read_text().splitlines()]
                    self.assertTrue(
                        {"login --help", "login --no-browser", "sts GetCallerIdentity"}
                        <= {call[0] for call in calls}
                    )
                    for command, *values in calls:
                        with self.subTest(command=command):
                            self.assertEqual(values, list(metadata.values()))
                finally:
                    self.run_helper("abort")

    def test_start_prints_device_block_without_mode(self) -> None:
        result = self.run_helper("start", "cn-beijing")
        self.assertEqual(result.returncode, 0, result.stderr)
        kv = self.kv(result.stdout)
        self.assertNotIn("MODE", kv)
        self.assertEqual(kv["URL"], "https://signin.volcengine.com/authorize/oauth/device?trace_id=trace-1")
        self.assertEqual(kv["CODE"], "ABCD-1234")
        self.assertEqual(kv["LINK"], "https://signin.volcengine.com/authorize/oauth/device?trace_id=trace-1&user_code=ABCD-1234")
        self.assertEqual(kv["EXPIRES_IN"], "300")
        self.assertIn("verify", kv["NEXT"])
        login_args = self.login_args.read_text(encoding="utf-8").split()
        self.assertEqual(login_args, ["login", "--no-browser", "--lang", "en", "--region", "cn-beijing"])

    def test_start_works_on_chinese_locale_by_pinning_lang(self) -> None:
        # Without --lang the real ve prints Chinese on a zh_CN locale and every
        # parsing anchor misses: start used to time out and kill ve (exit 6).
        result = self.run_helper("start", "cn-beijing", env_extra={"LANG": "zh_CN.UTF-8", "LC_ALL": "zh_CN.UTF-8"})
        self.assertEqual(result.returncode, 0, result.stderr)
        kv = self.kv(result.stdout)
        self.assertEqual(kv["CODE"], "ABCD-1234")
        self.assertEqual(kv["EXPIRES_IN"], "300")
        self.assertIn("--lang", self.login_args.read_text(encoding="utf-8").split())

    def test_url_and_status_while_alive(self) -> None:
        self.assertEqual(self.run_helper("start", "cn-beijing").returncode, 0)
        url = self.run_helper("url")
        self.assertEqual(url.returncode, 0, url.stderr)
        self.assertEqual(self.kv(url.stdout)["CODE"], "ABCD-1234")
        status = self.run_helper("status")
        self.assertEqual(status.returncode, 0)
        self.assertIn("ALIVE:", status.stdout)
        self.assertIn("url=yes", status.stdout)
        self.assertNotIn("mode=", status.stdout)

    def test_verify_pending_then_ok_with_profile(self) -> None:
        self.assertEqual(self.run_helper("start", "cn-beijing", "prod").returncode, 0)
        self.assertEqual(self.login_args.read_text(encoding="utf-8").split()[-2:], ["--profile", "prod"])
        pending = self.run_helper("verify", "prod")
        self.assertEqual(pending.returncode, 11, pending.stdout + pending.stderr)
        self.assertIn("PENDING", pending.stdout)
        self.assertIn("300s", pending.stdout)
        self.approve.write_text("ok", encoding="utf-8")
        ok = self.wait_for_exit(0, "verify", "prod")
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertIn("GetCallerIdentity verified for profile 'prod'", ok.stdout)
        # Service API calls use the two-hyphen system flag.
        self.assertEqual(self.sts_args.read_text(encoding="utf-8").split(), ["sts", "GetCallerIdentity", "--profile", "prod"])
        # State is cleaned up: url now reports no live process.
        self.assertEqual(self.run_helper("url").returncode, 3)

    def test_verify_without_profile_calls_plain_sts(self) -> None:
        self.assertEqual(self.run_helper("start", "cn-shanghai").returncode, 0)
        self.approve.write_text("ok", encoding="utf-8")
        ok = self.wait_for_exit(0, "verify")
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertEqual(self.sts_args.read_text(encoding="utf-8").split(), ["sts", "GetCallerIdentity"])

    def test_logged_in_but_api_unreachable_is_exit_13(self) -> None:
        self.assertEqual(self.run_helper("start", "cn-beijing").returncode, 0)
        self.approve.write_text("ok", encoding="utf-8")
        result = None
        for _ in range(20):
            result = self.run_helper("verify", env_extra={"FAKE_VE_STS_FAIL": "1"})
            if result.returncode != 11:
                break
            time.sleep(0.25)
        assert result is not None
        self.assertEqual(result.returncode, 13, result.stdout + result.stderr)
        self.assertIn("LOGGED_IN_UNVERIFIED", result.stdout)

    def test_denied_authorization_is_exit_10(self) -> None:
        self.assertEqual(self.run_helper("start", "cn-beijing").returncode, 0)
        self.approve.write_text("deny", encoding="utf-8")
        result = self.wait_for_exit(10, "verify")
        self.assertEqual(result.returncode, 10, result.stdout + result.stderr)
        self.assertIn("denied", result.stderr)

    def test_complete_is_rejected(self) -> None:
        self.assertEqual(self.run_helper("start", "cn-beijing").returncode, 0)
        result = self.run_helper("complete", "some-code")
        self.assertEqual(result.returncode, 2)
        self.assertIn("verify", result.stderr)

    def test_old_ve_without_device_flow_asks_to_upgrade(self) -> None:
        result = self.run_helper("start", "cn-beijing", env_extra={"FAKE_VE_MODE": "old"})
        self.assertEqual(result.returncode, 4)
        self.assertIn("@volcengine/cli@latest", result.stderr)
        self.assertFalse(self.login_args.exists(), "must not launch ve login on an unsupported build")

    def test_missing_ve_is_exit_4(self) -> None:
        # System dirs only: coreutils stay available, the fake (and any npm-installed) ve do not.
        bare_path = "/usr/bin:/bin"
        if shutil.which("ve", path=bare_path):
            self.skipTest("a real ve lives in /usr/bin or /bin")
        result = self.run_helper("start", "cn-beijing", env_extra={"PATH": bare_path})
        self.assertEqual(result.returncode, 4)
        self.assertIn("not found", result.stderr)

    def test_start_twice_is_refused_until_abort(self) -> None:
        self.assertEqual(self.run_helper("start", "cn-beijing").returncode, 0)
        again = self.run_helper("start", "cn-beijing")
        self.assertEqual(again.returncode, 3)
        self.assertIn("abort", again.stderr)
        self.assertEqual(self.run_helper("abort").returncode, 0)
        self.assertEqual(self.run_helper("status").returncode, 3)


if __name__ == "__main__":
    unittest.main()
