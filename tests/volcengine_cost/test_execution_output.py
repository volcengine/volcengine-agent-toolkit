from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "core" / "volcengine-cost" / "scripts"))

from cost_query.common.errors import BillingQueryError, ErrorCode, ExitCode  # noqa: E402
from cost_query.common.execution_output import (  # noqa: E402
    OUTPUT_PROTOCOL_VERSION,
    build_envelope,
    compact_size,
    error_envelope,
    write_json_result,
)
from cost_query.common.json_output import dumps  # noqa: E402


class ExecutionOutputTest(unittest.TestCase):
    def test_envelope_has_only_public_fields_and_required_machine_version(self) -> None:
        payload = build_envelope(
            status="success",
            message="查询成功。",
            result=[],
            meta={"action": "ListBill"},
        )
        self.assertEqual({"status", "message", "result", "_meta"}, set(payload))
        self.assertEqual(OUTPUT_PROTOCOL_VERSION, payload["_meta"]["output_protocol_version"])

    def test_error_envelope_keeps_exit_code_outside_json(self) -> None:
        error = BillingQueryError(
            ErrorCode.PERMISSION_DENIED,
            "当前身份无权限",
            ExitCode.QUERY_FAILED,
        )
        payload = error_envelope(error)
        self.assertEqual("error", payload["status"])
        self.assertIsNone(payload["result"])
        self.assertEqual("PERMISSION_DENIED", payload["_meta"]["error"]["code"])
        self.assertEqual(ExitCode.QUERY_FAILED, error.exit_code)

    def test_success_and_partial_require_non_null_business_result(self) -> None:
        for status in ("success", "partial"):
            with self.subTest(status=status), self.assertRaises(ValueError):
                build_envelope(status=status, message="message", result=None)

    def test_strict_json_rejects_nan_and_infinity(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                dumps({"value": value})

    def test_stdout_budget_counts_complete_envelope(self) -> None:
        small = build_envelope(status="success", message="ok", result=[{"value": "x"}])
        large = build_envelope(status="success", message="ok", result=[{"value": "x" * 1024}])
        self.assertGreater(compact_size(large), compact_size(small))
        self.assertEqual(len(dumps(small).encode("utf-8")), compact_size(small))

    def test_json_result_write_is_atomic_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            resolved = write_json_result(path, {"amount": "0.012091"}, overwrite=False)
            self.assertEqual({"amount": "0.012091"}, json.loads(resolved.read_text()))
            with self.assertRaises(FileExistsError):
                write_json_result(path, {"amount": "1"}, overwrite=False)


if __name__ == "__main__":
    unittest.main()
