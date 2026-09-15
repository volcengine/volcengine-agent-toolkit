"""Offline checks for caller metadata in the opt-in product CLI test runner."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import subprocess
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parent / "integration" / "verify_product_clis_live.py"
SPEC = importlib.util.spec_from_file_location("product_cli_live", SCRIPT)
assert SPEC and SPEC.loader
LIVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LIVE)


class ProductCliCallerMetadataTest(unittest.TestCase):
    def run_step(self, command, agent, skill, inherited):
        args = Namespace(ve="ve-under-test", agent_id=agent, skill_name=skill, timeout=1)
        suite = LIVE.LiveChecks(args)
        completed = subprocess.CompletedProcess([], 0, stdout="{}", stderr="")
        with (
            mock.patch.dict(LIVE.os.environ, inherited, clear=True),
            mock.patch.object(LIVE.subprocess, "run", return_value=completed) as run,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertTrue(suite.step("OFFLINE", command, "ve <test-command>", lambda _: {}))
        self.assertEqual(run.call_args.args[0], ["ve-under-test", *command])
        return run.call_args.kwargs["env"]

    def test_ark_uses_current_ve_metadata_without_duplicate_ark_prefix(self):
        inherited = {
            "VE_CALLER_TYPE": "old-type",
            "VE_CALLER_NAME": "old-agent",
            "VE_SKILL_NAME": "old-skill",
            "ARKCLI_NO_UPDATE_NOTIFIER": "1",
            "ARKCLI_CALLER_TYPE": "old-type",
            "ARKCLI_CALLER_NAME": "old-agent",
            "ARKCLI_SKILL_NAME": "arkcli-auth",
            "ARKCLI_TEST_SETTING": "preserve",
            "VOLCENGINE_PROFILE": "test-profile",
        }
        cases = [
            ("codex", "volcengine-cli"),
            ("claude-code", "volcengine-troubleshooting"),
            ("opencode", "volcengine-deploy"),
        ]
        for agent, skill in cases:
            with self.subTest(agent=agent, skill=skill):
                env = self.run_step(
                    ["arkcli", "auth", "status", "--profile", "test-profile"],
                    agent,
                    skill,
                    inherited,
                )
                self.assertEqual(env["VE_CALLER_TYPE"], "ai_agent")
                self.assertEqual(env["VE_CALLER_NAME"], agent)
                self.assertEqual(env["VE_SKILL_NAME"], skill)
                for name in (
                    "ARKCLI_CALLER_TYPE",
                    "ARKCLI_CALLER_NAME",
                    "ARKCLI_SKILL_NAME",
                    "ARKCLI_NO_UPDATE_NOTIFIER",
                ):
                    self.assertNotIn(name, env)
                self.assertEqual(env["ARKCLI_TEST_SETTING"], "preserve")
                self.assertEqual(env["VOLCENGINE_PROFILE"], "test-profile")

    def test_native_and_tos_commands_also_receive_current_ve_metadata(self):
        for command in (
            ["sts", "GetCallerIdentity"],
            ["tosutil", "ls"],
            ["version"],
            ["proxycli", "upgrade", "arkcli"],
        ):
            with self.subTest(command=command):
                env = self.run_step(command, "test-agent", "volcengine-cli", {})
                self.assertEqual(env["VE_CALLER_TYPE"], "ai_agent")
                self.assertEqual(env["VE_CALLER_NAME"], "test-agent")
                self.assertEqual(env["VE_SKILL_NAME"], "volcengine-cli")
                self.assertFalse(any(name.startswith("ARKCLI_") for name in env))


if __name__ == "__main__":
    unittest.main()
