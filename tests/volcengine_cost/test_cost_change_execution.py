from __future__ import annotations

import contextlib
import csv
import io
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "skills" / "core" / "volcengine-cost"
sys.path.insert(0, str(ROOT / "scripts"))

from cost_query.billing.client import VeBillingClient
from cost_query.billing.fetch import validate_response_payload
from cost_query.billing.guidance import action_selection_summary
from cost_query.billing.query_contract import query_contract
from cost_query.billing.schema import ACTION_SCHEMAS
from cost_query.billing.validation import validate_request_body
from cost_query.common.errors import BillingQueryError
from query_billing import main


class CostChangeExecutionTest(unittest.TestCase):
    def cases(self):
        common = {"CurrentPeriod": "2026-06-01", "BasePeriod": "2026-05-01", "Metric": 3}
        return (
            ("QueryCostChangeDimensions", {**common, "CandidateDimensions": ["product"]}),
            ("QueryCostChangeAmountComponents", {**common, "Filters": {"charge_item_code": "ci"}}),
            ("QueryCostChangeDrivers", {"current_period": "2026-06-01", "base_period": "2026-05-01",
                                        "Metric": "original_bill_amount", "filters": {"charge_item_code": "ci"}}),
        )

    def payload(self, action):
        if action.endswith("Drivers"):
            return {"total_diff": -20, "base_amount": 100, "current_amount": 80,
                    "contributions": [{"dimension": "usage", "dimension_name": "用量",
                                       "contribution": -20, "base_amount": 100, "current_amount": 80}]}
        return {"totalDiff": -20, "baseAmount": 100, "currentAmount": 80,
                "candidates": [{"dimension": "amount_component" if action.endswith("Components") else "product",
                                "coverageRatio": 1, "values": [{"valueKey": "refund", "deltaAmount": -20,
                                "baseAmount": 100, "currentAmount": 80, "contributionRatio": 1}]}]}

    def client(self, runner):
        return VeBillingClient(region="cn-beijing", profile="review", timeout_seconds=None,
                               executable=sys.executable, runner=runner)

    def invoke(self, directory, action, body, result, *extra):
        fixture = Path(directory) / f"{action}.json"
        fixture.write_text(json.dumps({"ResponseMetadata": {"RequestId": "request-review-123"}, "Result": result}))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["--action", action, "--body", json.dumps(body), "--fixture-dir", str(directory), *extra])
        return code, json.loads(output.getvalue())

    def test_only_cost_change_actions_use_force_post_and_explicit_api_version(self):
        for action, body in (*self.cases(), ("QueryBalanceAcct", {})):
            with self.subTest(action=action):
                calls = []
                def runner(command, **kwargs):
                    calls.append((command, kwargs))
                    return subprocess.CompletedProcess(command, 0, '{"Result":{}}', "")
                self.client(runner).query(action, body)
                command, kwargs = calls[0]
                if action == "QueryBalanceAcct":
                    self.assertNotIn("--force", command)
                else:
                    self.assertIn("--force", command)
                    self.assertEqual("2022-01-01", command[command.index("--version") + 1])
                    self.assertEqual("POST", command[command.index("--method") + 1])
                    self.assertEqual("Content-Type=application/json", command[command.index("--header") + 1])
                    self.assertEqual("json", command[command.index("--output") + 1])
                self.assertEqual(body, json.loads(command[command.index("--body") + 1]))
                self.assertEqual("review", command[command.index("---profile") + 1])
                self.assertFalse(kwargs["check"])

    def test_unknown_force_option_reports_upgrade_without_retry_or_fallback(self):
        calls = []
        def runner(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 2, "", "unknown flag: --force")
        action, body = self.cases()[0]
        with self.assertRaises(BillingQueryError) as raised:
            self.client(runner).query(action, body)
        self.assertEqual("VE_CLI_UPGRADE_REQUIRED", raised.exception.code.value)
        self.assertIn("升级到支持 --force 的版本", str(raised.exception))
        self.assertEqual(1, len(calls))

    def test_base_resp_failure_is_not_a_successful_analysis(self):
        action, body = self.cases()[0]
        result = {**self.payload(action), "BaseResp": {"StatusCode": 500, "StatusMessage": "analysis failed"}}
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, json.dumps({
                "ResponseMetadata": {"RequestId": "request-review-123"}, "Result": result}), "")
        with self.assertRaises(BillingQueryError) as raised:
            self.client(runner).query(action, body)
        self.assertEqual("500", raised.exception.cause["remote_code"])
        self.assertEqual("request-review-123", raised.exception.cause["request_id"])

    def test_invalid_required_amounts_and_lists_are_rejected(self):
        for action, _ in self.cases():
            payload = self.payload(action)
            amount = "total_diff" if action.endswith("Drivers") else "totalDiff"
            items = "contributions" if action.endswith("Drivers") else "candidates"
            missing = dict(payload)
            del missing[amount]
            bad_cases = [missing, {**payload, items: "invalid"}]
            bad_cases.extend({**payload, amount: value} for value in (None, True, "20", float("inf"), float("nan")))
            for invalid in bad_cases:
                with self.subTest(action=action, invalid=repr(invalid)), self.assertRaises(BillingQueryError):
                    validate_response_payload(action, invalid)

    def test_invalid_nested_contributions_are_rejected(self):
        for action, _ in self.cases():
            invalid = self.payload(action)
            if action.endswith("Drivers"):
                del invalid["contributions"][0]["contribution"]
            else:
                invalid["candidates"][0]["values"][0]["deltaAmount"] = True
            with self.subTest(action=action), self.assertRaises(BillingQueryError):
                validate_response_payload(action, invalid)

    def test_cli_returns_nested_data_without_pagination_or_workflow(self):
        with tempfile.TemporaryDirectory() as directory:
            for action, body in self.cases():
                with self.subTest(action=action):
                    result = self.payload(action)
                    code, output = self.invoke(directory, action, body, result)
                    self.assertEqual(0, code, output)
                    self.assertEqual("success", output["status"])
                    record = {key: value for key, value in output["result"][0].items() if not key.startswith("_")}
                    self.assertEqual(result, record)

    def test_explicit_csv_preserves_nested_arrays_as_json(self):
        with tempfile.TemporaryDirectory() as directory:
            for action, body in self.cases():
                with self.subTest(action=action):
                    result = self.payload(action)
                    path = Path(directory) / f"{action}.csv"
                    code, output = self.invoke(directory, action, body, result, "--out", str(path))
                    self.assertEqual(0, code, output)
                    key = "contributions" if action.endswith("Drivers") else "candidates"
                    with path.open(newline="") as file:
                        rows = list(csv.DictReader(file))
                    self.assertEqual(result[key], json.loads(rows[0][key]))
                    self.assertTrue(Path(output["result"]["fields"]).is_file())

    def test_large_result_automatically_writes_recoverable_nested_data(self):
        action, body = self.cases()[0]
        result = self.payload(action)
        result["candidates"][0]["values"][0]["valueName"] = "large-result-" * 6000
        with tempfile.TemporaryDirectory() as directory:
            # Scope the existing automatic temp-output location to this test.
            from unittest.mock import patch
            with patch("query_billing.tempfile.gettempdir", return_value=directory):
                code, output = self.invoke(directory, action, body, result)
            self.assertEqual(0, code, output)
            with Path(output["result"]["file"]).open(newline="") as file:
                row = next(csv.DictReader(file))
            self.assertEqual(result["candidates"], json.loads(row["candidates"]))

    def test_invalid_dimensions_and_missing_charge_item_fail_before_call(self):
        action, body = self.cases()[0]
        for dimensions in ([], ["product", "project"], ["unknown"]):
            with self.subTest(dimensions=dimensions), self.assertRaises(BillingQueryError):
                validate_request_body(action, {**body, "CandidateDimensions": dimensions})
        for action, body in self.cases()[1:]:
            key = "filters" if action.endswith("Drivers") else "Filters"
            with self.subTest(action=action), self.assertRaises(BillingQueryError):
                validate_request_body(action, {**body, key: {}})

    def test_explicit_null_scope_filters_fail_before_remote_call(self):
        for action, body in self.cases():
            key = "filters" if action.endswith("Drivers") else "Filters"
            for field in ("product", "project", "region_code", "instance_no", "charge_item_code"):
                with self.subTest(action=action, field=field):
                    calls = []
                    def runner(command, **kwargs):
                        calls.append(command)
                        return subprocess.CompletedProcess(command, 0, '{"Result":{}}', "")
                    request = {**body, key: {**body.get(key, {}), field: None}}
                    with self.assertRaises(BillingQueryError) as raised:
                        self.client(runner).query(action, request)
                    self.assertEqual("INVALID_ARGUMENT", raised.exception.code.value)
                    paths = {item["path"] for item in raised.exception.details["invalid_parameters"]}
                    self.assertIn(f"{key}.{field}", paths)
                    self.assertEqual([], calls)

    def test_omitted_scope_filters_remain_valid(self):
        for action, body in self.cases():
            with self.subTest(action=action):
                self.assertEqual(body, validate_request_body(action, body))

    def test_null_candidate_lists_are_valid_but_missing_lists_are_not(self):
        with tempfile.TemporaryDirectory() as directory:
            for action, body in self.cases():
                key = "contributions" if action.endswith("Drivers") else "candidates"
                result = {**self.payload(action), key: None}
                with self.subTest(action=action):
                    code, output = self.invoke(directory, action, body, result)
                    self.assertEqual(0, code, output)
                    self.assertIsNone(output["result"][0][key])
                    del result[key]
                    with self.assertRaises(BillingQueryError):
                        validate_response_payload(action, result)

    def test_nested_null_values_list_is_valid(self):
        action, body = self.cases()[0]
        result = self.payload(action)
        result["candidates"][0]["values"] = None
        with tempfile.TemporaryDirectory() as directory:
            code, output = self.invoke(directory, action, body, result)
            self.assertEqual(0, code, output)

    def test_current_month_freshness_covers_either_comparison_period(self):
        with tempfile.TemporaryDirectory() as directory:
            for action, body in self.cases():
                key = "base_period" if action.endswith("Drivers") else "BasePeriod"
                current = {**body, key: date.today().strftime("%Y-%m-01")}
                code, output = self.invoke(directory, action, current, self.payload(action))
                self.assertEqual(0, code, output)
                self.assertTrue(output["_meta"]["freshness"]["partial_period"])

    def test_discovery_documents_nonpaged_analysis_and_usage(self):
        contract = query_contract()
        for action, _ in self.cases():
            with self.subTest(action=action):
                self.assertIn(action, contract["pagination"]["none"]["actions"])
                guidance = action_selection_summary(ACTION_SCHEMAS[action])
                self.assertTrue(guidance["use_when"])
                self.assertTrue(guidance["avoid_when"])
                self.assertTrue(guidance["important_limits"])


if __name__ == "__main__":
    unittest.main()
