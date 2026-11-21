from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "core" / "volcengine-cost" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import cost
from cost_query.common.errors import ExitCode


class CostCheckTest(unittest.TestCase):
    def run_check(self, *, ve_path="/mock/ve", ve_returncode=0, ve_stderr="",
                  python_version=(3, 10, 0), module_error=None):
        output = io.StringIO()
        with patch.object(cost.sys, "version_info", python_version), \
                patch.object(cost.importlib, "import_module", side_effect=module_error), \
                patch.object(cost.shutil, "which", return_value=ve_path), \
                patch.object(cost.subprocess, "run", return_value=subprocess.CompletedProcess(
                    ["/mock/ve", "version"], ve_returncode, "ve version 1.1.10\n", ve_stderr)), \
                contextlib.redirect_stdout(output):
            exit_code = cost.main(["check"])
        return exit_code, json.loads(output.getvalue())

    def test_healthy_dependencies_report_ok_with_credentials_unverified(self):
        with patch("pathlib.Path.home", side_effect=AssertionError("must not inspect credentials")):
            exit_code, payload = self.run_check()
        self.assertEqual(int(ExitCode.SUCCESS), exit_code)
        for name in ("python", "command_modules", "ve_cli"):
            self.assertEqual("pass", payload["dependencies"][name]["status"])
        self.assertEqual("skip", payload["dependencies"]["credentials"]["status"])
        self.assertFalse(payload["dependencies"]["credentials"]["verified"])
        self.assertEqual("ok", payload["status"])

    def test_missing_ve_cli_still_reports_degraded(self):
        exit_code, payload = self.run_check(ve_path=None)
        self.assertEqual(int(ExitCode.SUCCESS), exit_code)
        self.assertEqual("warn", payload["dependencies"]["ve_cli"]["status"])
        self.assertEqual("degraded", payload["status"])

    def test_ve_cli_warning_still_reports_degraded(self):
        for arguments in ({"ve_returncode": 1}, {"ve_stderr": "version warning"}):
            with self.subTest(**arguments):
                exit_code, payload = self.run_check(**arguments)
                self.assertEqual(int(ExitCode.SUCCESS), exit_code)
                self.assertEqual("warn", payload["dependencies"]["ve_cli"]["status"])
                self.assertEqual("degraded", payload["status"])

    def test_dependency_failure_takes_precedence_over_warning_and_skip(self):
        for name, arguments in (
            ("python", {"python_version": (3, 9, 0)}),
            ("command_modules", {"module_error": ModuleNotFoundError("missing module")}),
        ):
            with self.subTest(dependency=name):
                exit_code, payload = self.run_check(ve_path=None, **arguments)
                self.assertEqual(int(ExitCode.DEPENDENCY_ERROR), exit_code)
                self.assertEqual("fail", payload["dependencies"][name]["status"])
                self.assertEqual("failed", payload["status"])


if __name__ == "__main__":
    unittest.main()
