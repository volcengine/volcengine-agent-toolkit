"""Portable, offline regressions for the contributed Skill."""

from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2] / "skills" / "core" / "volcengine-cost"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import cost
import query_billing
import test_coupon_attribution as coupon_examples
import test_reconcile_cost as reconcile_examples
import test_resource_package_attribution as package_examples
from cost_query.arrears.coupon import analyze_coupon_attribution
from cost_query.arrears.input_evidence import load_attribution_input
from cost_query.arrears.resource_package import analyze_resource_package_attribution
from cost_query.billing.client import VeBillingClient
from cost_query.billing.json_schema import schema_contract
from cost_query.billing.validation import validate_request_body
from cost_query.common.errors import BillingQueryError
from cost_query.utils.redaction import redact_diagnostic, redact_text
from cost_query.reconciliation.engine import DrillDownRequest, drill_down


class RuntimeInstallTest(unittest.TestCase):
    def test_copied_skill_runs_without_site_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            installed = Path(directory) / "volcengine-cost"
            shutil.copytree(ROOT, installed, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            commands = (
                ["schema", "--list-actions"],
                ["query", "--action", "QueryBalanceAcct", "--body", "{}",
                 "--fixture-dir", str(Path(__file__).resolve().parent / "fixtures/query_balance_acct/current_arrears")],
            )
            for arguments in commands:
                completed = subprocess.run(
                    [sys.executable, "-S", "scripts/cost.py", *arguments], cwd=installed,
                    capture_output=True, text=True, env={**os.environ, "PATH": "/usr/bin:/bin"},
                )
                self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
                payload = json.loads(completed.stdout)
                if arguments[0] == "schema":
                    self.assertEqual(19, len(payload["actions"]))
                else:
                    self.assertEqual("success", payload["status"])
                    self.assertNotIn("AccountID", payload["result"])

    def test_dependency_check_does_not_inspect_credential_config(self):
        with patch("pathlib.Path.home", side_effect=AssertionError("credential config must not be read")), \
                patch.object(cost.shutil, "which", return_value=sys.executable), \
                patch.object(cost.subprocess, "run", return_value=subprocess.CompletedProcess(
                    [sys.executable, "version"], 0, "1.1.10\n", "")):
            result = cost._check()
        self.assertFalse(result["dependencies"]["credentials"]["verified"])
        self.assertEqual("pass", result["dependencies"]["ve_cli"]["status"])
        self.assertEqual("1.1.10", result["dependencies"]["ve_cli"]["version"])

    def test_query_uses_existing_region_when_none_was_selected(self):
        commands = []
        def runner(command, **kwargs):
            commands.append(command)
            return subprocess.CompletedProcess(command, 0, '{"Result":{}}', "")
        client = VeBillingClient(region=None, profile=None, timeout_seconds=None,
                                 executable=sys.executable, runner=runner)
        client.query("QueryBalanceAcct", {})
        self.assertNotIn("---region", commands[0])

    def test_plain_and_nested_diagnostics_redact_standard_credentials(self):
        secret = "SYNTHETIC_SECRET_VALUE"
        def runner(command, **kwargs):
            output = json.dumps({"ResponseMetadata": {"Error": {"Code": "AccessDenied", "Message": "denied"}},
                                 "Diagnostic": {key: secret for key in ("SecretAccessKey", "AccessKeyId", "SecurityToken", "Cookie")}})
            return subprocess.CompletedProcess(command, 1, output, f"SecurityToken={secret}")
        client = VeBillingClient(region=None, profile=None, timeout_seconds=None,
                                 executable=sys.executable, runner=runner)
        with self.assertRaises(BillingQueryError) as raised:
            client.query("QueryBalanceAcct", {})
        self.assertNotIn(secret, json.dumps(raised.exception.error_dict()))
        with self.assertRaises(BillingQueryError) as raised:
            validate_request_body("ListBillDetail", {"BillPeriod": "2026-09", "Limit": 1,
                                                    "TagKV": {"SecretAccessKey": secret}})
        self.assertNotIn(secret, json.dumps(raised.exception.error_dict()))

    def test_schema_exposes_array_and_nested_required_constraints(self):
        schema = schema_contract("QueryCostChangeDimensions", section="request")["request_json_schema"]
        dimensions = schema["properties"]["CandidateDimensions"]
        self.assertEqual(1, dimensions["minItems"])
        self.assertIn("product", dimensions["items"]["enum"])
        schema = schema_contract("QueryCostChangeAmountComponents", section="request")["request_json_schema"]
        self.assertIn("charge_item_code", schema["properties"]["Filters"]["required"])

    def test_cookie_headers_redact_every_cookie_value(self):
        for name in ("Cookie", "Set-Cookie"):
            value = f"{name}: sessionid=SYNTHETIC_FIRST; sessionid_ss=SYNTHETIC_SECOND"
            self.assertNotIn("SYNTHETIC", redact_text(value))
            structured = {name: "sessionid=SYNTHETIC_FIRST; sessionid_ss=SYNTHETIC_SECOND"}
            self.assertNotIn("SYNTHETIC", json.dumps(redact_diagnostic(structured)))
            self.assertNotIn("SYNTHETIC", redact_text(json.dumps(structured)))

    def test_snake_case_grain_cannot_bypass_required_field_check(self):
        with tempfile.TemporaryDirectory() as directory:
            args = query_billing.build_parser().parse_args([
                "--action", "ListBillDetail", "--body",
                '{"bill_period":"2026-09","group_period":2,"group_term":1}',
                "--pagination", "page", "--require-field", "Count", "--fixture-dir", directory,
            ])
            with self.assertRaises(BillingQueryError) as raised:
                query_billing.run(args)
            self.assertEqual("RESPONSE_FIELD_NOT_PRESERVED", raised.exception.code.value)

    def test_snake_case_pagination_preserves_requested_page(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ListBill__period-2026-09__offset-4.json").write_text(json.dumps({
                "Result": {"List": [{"BillID": "synthetic-bill", "PayableAmount": "1", "Currency": "CNY"}],
                           "Limit": 2, "Offset": 4, "Total": 6},
            }))
            args = query_billing.build_parser().parse_args([
                "--action", "ListBill", "--body", '{"bill_period":"2026-09","limit":2,"offset":4}',
                "--pagination", "page", "--fixture-dir", directory,
            ])
            code, result = query_billing.run(args)
            self.assertEqual(0, code)
            self.assertEqual("synthetic-bill", result["result"][0]["BillID"])

    def test_json_money_keeps_ten_decimal_places_in_query_and_attribution(self):
        raw = "123456789.1234567891"
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, '{"Result":{"amount":'+raw+'}}', "")
        client = VeBillingClient(region=None, profile=None, timeout_seconds=None,
                                 executable=sys.executable, runner=runner)
        self.assertEqual(Decimal(raw), client.query("QueryBalanceAcct", {})["Result"]["amount"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text('{"rows":[{"PayableAmount":'+raw+'}]}')
            self.assertEqual(Decimal(raw), load_attribution_input(path, input_name="bill_details").rows[0]["PayableAmount"])

    def test_unknown_coupon_rule_does_not_prove_nonapplicability(self):
        example = coupon_examples.CouponAttributionTest()
        example.setUp()
        coupon = dict(example.coupons[0])
        coupon.pop("AmountLimit", None)
        result = analyze_coupon_attribution(coupons=[coupon], bill_details=example.bills,
                                           analysis_period="2026-09", candidate_coupon_ids=[coupon["CouponID"]])
        self.assertNotIn("coupon_not_applicable", {item["reason_type"] for item in result["supported_reasons"]})
        self.assertTrue(any(item["candidate"] == "coupon_applicability" for item in result["insufficient_evidence"]))

    def test_invalid_current_redemption_is_unknown(self):
        example = coupon_examples.CouponAttributionTest()
        example.setUp()
        coupon_id = example.coupons[0]["CouponID"]
        records = [{"CouponID": coupon_id, "BillingCycle": period, "ChangeType": 2, "ChangeAmount": amount}
                   for period, amount in (("2026-08", "500"), ("2026-09", None))]
        result = analyze_coupon_attribution(coupons=example.coupons, bill_details=example.bills,
                                           usage_records=records, analysis_period="2026-09", comparison_period="2026-08")
        self.assertNotIn("coupon_redemption_declined", {item["reason_type"] for item in result["supported_reasons"]})
        self.assertIsNone(result["coupon_usage_summaries"][0]["periods"]["2026-09"]["redeemed_amount"])

    def test_refunded_package_is_not_marked_used_up(self):
        example = package_examples.ResourcePackageAttributionTest()
        example.setUp()
        packages = [dict(row, Status="Refunded", AvailableAmount="0") for row in example.packages]
        result = analyze_resource_package_attribution(packages=packages, usage_details=example.usage,
                                                      bill_details=example.bills, analysis_period="2026-09")
        self.assertNotIn("resource_package_used_up", {item["reason_type"] for item in result["supported_reasons"]})

    def test_package_usage_follows_bill_consumption_intervals(self):
        example = package_examples.ResourcePackageAttributionTest()
        example.setUp()
        bills = [dict(row) for row in example.bills]
        bills[0].update(ExpenseBeginTime="2026-09-01T00:00:00Z", ExpenseEndTime="2026-10-01T00:00:00Z")
        bills[1].update(ExpenseBeginTime="2026-10-01T00:00:00Z", ExpenseEndTime="2026-11-01T00:00:00Z")
        usages = [dict(row) for row in example.usage]
        for row in usages:
            if row["BeginTime"].startswith("2026-08"):
                row.update(BeginTime="2026-09-01T00:00:00Z", EndTime="2026-10-01T00:00:00Z", DeductionUseAmount="1")
            else:
                row.update(BeginTime="2026-10-01T00:00:00Z", EndTime="2026-11-01T00:00:00Z", DeductionUseAmount="10")
        result = analyze_resource_package_attribution(packages=example.packages, usage_details=usages,
                                                      bill_details=bills, analysis_period="2026-09", comparison_period="2026-08")
        self.assertNotIn("resource_package_deduction_declined", {item["reason_type"] for item in result["supported_reasons"]})

    def test_reconciliation_rejects_another_csvs_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            example = reconcile_examples.ReconcileCostTest()
            left, right = example._detail_split(root)
            other = reconcile_examples.write_query_artifact(root, "other", "ListBillDetail", ["Product", "PayableAmount", "Currency"],
                                                            [{"Product": "ECS", "PayableAmount": "1", "Currency": "CNY"}])
            code, result, _ = example._run(["preflight", "--left", str(other), "--left-metadata", str(left.with_suffix(".meta.json")),
                                      "--right", str(right), "--group-by", "Product"])
            self.assertEqual(0, code)
            self.assertEqual("block", result["verdict"])
            output = root / "comparison.csv"
            code, result, _ = example._run([
                "run", "--left", str(other), "--left-metadata", str(left.with_suffix(".meta.json")),
                "--right", str(right), "--group-by", "Product", "--mode", "observational", "--out", str(output),
            ])
            self.assertEqual(0, code)
            self.assertEqual("observational", result["_meta"]["claim_scope"])
            self.assertIn("与实际输入不一致", result["message"])

    def test_repeated_single_side_drill_down_keeps_conservation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            example = reconcile_examples.ReconcileCostTest()
            left, right = example._detail_split(root)
            parent = root / "parent.csv"
            code, _, _ = example._run(["run", "--left", str(left), "--right", str(right), "--group-by", "Product", "--out", str(parent)])
            self.assertEqual(0, code)
            child = root / "child.csv"
            drill_down(DrillDownRequest(parent, (("Product", "ECS"), ("Currency", "CNY")), ("InstanceNo",), "right"), child)
            result = drill_down(DrillDownRequest(child, (("InstanceNo", "i-1"),), ("Project",), "right"), root / "grandchild.csv")
            self.assertEqual("matched", result["conservation"]["status"])

    def test_failed_conservation_downgrades_every_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            example = reconcile_examples.ReconcileCostTest()
            left, right = example._detail_split(root)
            parent = root / "parent.csv"
            code, _, _ = example._run(["run", "--left", str(left), "--right", str(right), "--group-by", "Product", "--out", str(parent)])
            self.assertEqual(0, code)
            for path in (left, right):
                with path.open(newline="") as file:
                    reader = csv.DictReader(file)
                    columns, rows = reader.fieldnames, list(reader)
                for row in rows:
                    if row["Product"] == "ECS":
                        row["PayableAmount"] = "200"
                with path.open("w", newline="") as file:
                    writer = csv.DictWriter(file, fieldnames=columns)
                    writer.writeheader(); writer.writerows(rows)
            child = root / "child.csv"
            code, payload, _ = example._run(["drill-down", "--from", str(parent), "--row", "Product=ECS", "--row", "Currency=CNY",
                                           "--by", "InstanceNo", "--side", "both", "--out", str(child)])
            self.assertEqual(0, code)
            self.assertEqual("partial", payload["status"])
            self.assertEqual("warn", payload["_meta"]["verdict"])
            self.assertIn("守恒", payload["message"])
            self.assertTrue(all(row["status"] == "inconclusive" and row["claim_scope"] == "inconclusive"
                                for row in reconcile_examples.read_csv(child)))
            grandchild = root / "grandchild.csv"
            code, payload, _ = example._run([
                "drill-down", "--from", str(child), "--row", "InstanceNo=i-1",
                "--by", "Element", "--side", "both", "--out", str(grandchild),
            ])
            self.assertEqual(0, code)
            self.assertEqual("partial", payload["status"])
            self.assertEqual("inconclusive", payload["_meta"]["claim_scope"])


if __name__ == "__main__":
    unittest.main()
