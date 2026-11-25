"""Offline smoke tests for the billing and cost management Skill and its critical evidence boundaries."""

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
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1] / "skills/core/volcengine-billing-and-cost-management"
sys.path.insert(0, str(ROOT / "scripts"))

from cost import main  # noqa: E402
from cost_query.arrears.input_evidence import load_attribution_input  # noqa: E402
from cost_query.billing.client import FixtureBillingClient  # noqa: E402
from cost_query.billing.json_schema import schema_contract  # noqa: E402


class VolcengineBillingAndCostManagementTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.client = FixtureBillingClient(self.root)

    def write_fixture(self, name: str, result: dict) -> None:
        response = result if name.startswith(("ListCoupons", "ListCouponUsageRecords")) else {"Result": result}
        (self.root / f"{name}.json").write_text(json.dumps(response), encoding="utf-8")

    def query(self, action: str, body: dict, *options: str) -> tuple[int, dict]:
        stdout = io.StringIO()
        with mock.patch("query_billing.FixtureBillingClient", return_value=self.client), contextlib.redirect_stdout(stdout):
            code = main(["query", "--action", action, "--body", json.dumps(body),
                         "--fixture-dir", str(self.root), *options])
        return code, json.loads(stdout.getvalue())

    def test_page_limit_conflict_is_rejected_before_any_request(self) -> None:
        for action, body in (("ListBill", {"BillPeriod": "2026-08", "Limit": 2}),
                             ("ListResourcePackages", {"ResourceType": "Package", "MaxResults": "2"})):
            with self.subTest(action=action):
                code, payload = self.query(action, body, "--pagination", "page", "--max-rows", "1")
                self.assertEqual(2, code)
                self.assertEqual("error", payload["status"])
                self.assertEqual([], self.client.calls)

    def test_page_preserves_explicit_limit_and_offset(self) -> None:
        self.write_fixture("ListBill", {"List": [{"BillID": "synthetic-bill"}],
                                       "Total": 10, "Limit": 2, "Offset": 4})
        code, payload = self.query("ListBill", {"BillPeriod": "2026-08", "Limit": 2, "Offset": 4},
                                   "--pagination", "page", "--max-rows", "2")
        self.assertEqual(0, code)
        self.assertEqual((2, 4), (self.client.calls[0]["body"]["Limit"], self.client.calls[0]["body"]["Offset"]))
        self.assertTrue(payload["_meta"]["coverage"]["requested_scope_fulfilled"])
        self.assertFalse(payload["_meta"]["coverage"]["is_complete"])

    def test_expanded_page_over_limit_is_partial_in_stdout_and_metadata(self) -> None:
        self.write_fixture("ListCostAnalysisOpenApi", {
            "CostData": [{"ClassifyItem": "ECS", "Costs": [
                {"TimeStr": "2026-08", "Amount": "10"},
                {"TimeStr": "2026-09", "Amount": "15"},
            ]}], "Total": 1, "Limit": 1, "Offset": 0,
        })
        output = self.root / "result.csv"
        body = {"CostType": 2, "TimeGranularity": 0, "BeginTimeStr": "2026-08-01",
                "EndTimeStr": "2026-09-01", "ClassifyDimension": 3}
        code, payload = self.query("ListCostAnalysisOpenApi", body, "--pagination", "page",
                                   "--page-size", "1", "--max-rows", "1", "--out", str(output))
        self.assertEqual(6, code)
        self.assertEqual("partial", payload["status"])
        metadata = json.loads(output.with_suffix(".meta.json").read_text())
        self.assertFalse(metadata["coverage"]["requested_scope_fulfilled"])
        self.assertFalse(metadata["coverage"]["is_complete"])
        self.assertEqual("max_rows", metadata["coverage"]["queries"][0]["stop_reason"])
        self.assertEqual(1, len(metadata["coverage"]["failed_queries"]))
        with output.open(newline="", encoding="utf-8") as file:
            self.assertEqual(1, len(list(csv.DictReader(file))))
        self.assertEqual(1, self.client.calls[0]["body"]["Limit"])

    def test_response_cursor_can_be_used_to_query_the_next_page(self) -> None:
        self.write_fixture("ListResourcePackages__token-start", {
            "List": [{"InstanceNo": "synthetic-one"}], "NextToken": "p2", "MaxResults": "1"})
        self.write_fixture("ListResourcePackages__token-p2", {
            "List": [{"InstanceNo": "synthetic-two"}], "NextToken": "0", "MaxResults": "1"})
        body = {"ResourceType": "Package", "MaxResults": "1"}
        code, first = self.query("ListResourcePackages", body, "--pagination", "page")
        self.assertEqual(0, code)
        cursor = first["_meta"]["coverage"]["queries"][0]
        self.assertEqual("p2", cursor["next_token"])
        self.assertTrue(cursor["has_more"])
        code, second = self.query("ListResourcePackages", {**body, "NextToken": cursor["next_token"]},
                                  "--pagination", "page")
        self.assertEqual(0, code)
        self.assertEqual("synthetic-two", second["result"][0]["InstanceNo"])
        self.assertEqual("", second["_meta"]["coverage"]["queries"][0]["next_token"])
        self.assertFalse(second["_meta"]["coverage"]["queries"][0]["has_more"])
        self.assertEqual("1", self.client.calls[0]["body"]["MaxResults"])

    def test_file_delivery_preserves_response_cursor(self) -> None:
        self.write_fixture("ListResourcePackages", {
            "List": [{"InstanceNo": "synthetic-one"}], "NextToken": "p2", "MaxResults": "1"})
        output = self.root / "packages.csv"
        code, payload = self.query("ListResourcePackages", {"ResourceType": "Package", "MaxResults": "1"},
                                   "--pagination", "page", "--out", str(output))
        self.assertEqual(0, code)
        metadata = json.loads(Path(payload["result"]["metadata"]).read_text())
        self.assertEqual("p2", metadata["coverage"]["queries"][0]["next_token"])

    def test_oversized_token_response_has_no_safe_resume_cursor(self) -> None:
        self.write_fixture("ListResourcePackages", {
            "List": [{"InstanceNo": "synthetic-one"}, {"InstanceNo": "synthetic-two"}],
            "NextToken": "p2", "MaxResults": "1"})
        code, payload = self.query("ListResourcePackages", {"ResourceType": "Package", "MaxResults": "1"},
                                   "--pagination", "page", "--max-rows", "1")
        self.assertEqual(6, code)
        coverage = payload["_meta"]["coverage"]
        self.assertFalse(coverage["requested_scope_fulfilled"])
        self.assertIsNone(coverage["queries"][0]["next_token"])
        self.assertIsNone(coverage["queries"][0]["has_more"])

    def test_project_filter_requires_explicit_detail_grain(self) -> None:
        for action in ("ListBillDetail", "ListSplitBillDetail"):
            self.write_fixture(action, {"List": [], "Total": 0, "Limit": 1, "Offset": 0})
            body = {"BillPeriod": "2026-08", "Limit": 1, "Project": ["synthetic-project"]}
            for grain in (None, 0, 2):
                with self.subTest(action=action, grain=grain):
                    request = body if grain is None else {**body, "GroupPeriod": grain}
                    before = len(self.client.calls)
                    code, payload = self.query(action, request, "--pagination", "page")
                    self.assertEqual(0 if grain == 2 else 2, code)
                    self.assertEqual(before + (grain == 2), len(self.client.calls))

    def test_nested_response_fields_preserve_ancestor_structure(self) -> None:
        for field in ("Amount", "CostData.Costs.Amount", "CostData[].Costs[].Amount"):
            with self.subTest(field=field):
                payload = schema_contract("ListCostAnalysisOpenApi", section="response", field_queries=[field])
                schema = payload["response_json_schema"]
                costs = schema["properties"]["CostData"]["items"]["properties"]["Costs"]
                self.assertEqual({"Amount"}, set(costs["items"]["properties"]))
        for action, field in (("ListBillOverviewByCategory", "PayableAmount"),
                              ("QueryCostChangeDimensions", "deltaAmount")):
            with self.subTest(action=action):
                self.assertIn(field, json.dumps(schema_contract(action, section="response", field_queries=[field])))

    def run_cli(self, arguments: list[str], expected: int = 0) -> dict:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(arguments)
        self.assertEqual(expected, code, stdout.getvalue() + stderr.getvalue())
        return json.loads(stdout.getvalue())

    def query_file(self, action: str, body: dict, name: str) -> tuple[Path, Path]:
        output = self.root / f"{name}.csv"
        code, payload = self.query(action, body, "--pagination", "full", "--out", str(output))
        self.assertEqual(0, code, payload)
        envelope = self.root / f"{name}.json"
        envelope.write_text(json.dumps(payload), encoding="utf-8")
        return output, envelope

    def test_copied_skill_runs_without_site_packages_or_ve(self) -> None:
        self.write_fixture("QueryBalanceAcct", {
            "AccountID": "synthetic-account", "AvailableBalance": "-10.50",
            "ArrearsBalance": "10.50", "CashBalance": "0", "CreditLimit": "0",
            "FreezeAmount": "0", "Currency": "CNY",
        })
        installed = self.root / "installed"
        shutil.copytree(ROOT, installed, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for arguments in (["schema", "--list-actions"],
                          ["query", "--action", "QueryBalanceAcct", "--body", "{}",
                           "--fixture-dir", str(self.root)]):
            with self.subTest(command=arguments[0]):
                result = subprocess.run(
                    [sys.executable, "-S", "scripts/cost.py", *arguments], cwd=installed,
                    capture_output=True, text=True, timeout=30,
                    env={**os.environ, "PATH": str(self.root / "no-binaries")},
                )
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                payload = json.loads(result.stdout)
                if arguments[0] == "schema":
                    self.assertEqual(19, len(payload["actions"]))
                else:
                    self.assertEqual("success", payload["status"])
                    self.assertNotIn("AccountID", payload["result"])
                    self.assertEqual("-10.50", payload["result"]["AvailableBalance"])

    def test_query_files_preserve_attribution_evidence_and_outer_limits(self) -> None:
        cases = (("ListCoupons", {}, "coupons", [{"CouponID": "synthetic-coupon"}]),
                 ("ListResourcePackages", {"ResourceType": "Package"}, "packages",
                  [{"InstanceNo": "synthetic-package", "Product": "TOS"}]))
        for action, body, name, rows in cases:
            with self.subTest(action=action):
                self.write_fixture(action, {"List": rows, "Total": 1, "Limit": 10,
                                            "Offset": 0, "NextToken": "0"})
                csv_path, envelope = self.query_file(action, body, name)
                from_csv = load_attribution_input(csv_path, input_name=name)
                from_file = load_attribution_input(envelope, input_name=name)
                self.assertEqual("complete", from_file.completeness)
                self.assertEqual(1, len(from_file.rows))
                self.assertEqual(rows[0], {key: from_file.rows[0][key] for key in rows[0]})
                self.assertEqual(from_csv.rows, from_file.rows)
                original = json.loads(envelope.read_text())
                for change, expected in (({"status": "partial"}, "partial"),
                                         ({"_meta": {"output_protocol_version": "unsupported"}}, "unknown"),
                                         ({"_meta": {"freshness": {"partial_period": True}}}, "partial")):
                    limited = {**original, **change}
                    if "_meta" in change:
                        limited["_meta"] = {**original["_meta"], **change["_meta"]}
                    envelope.write_text(json.dumps(limited), encoding="utf-8")
                    self.assertEqual(expected, load_attribution_input(envelope, input_name=name).completeness)

    def test_attribution_rejects_metadata_from_another_query(self) -> None:
        self.write_fixture("ListCoupons", {"List": [{"CouponID": "synthetic-coupon"}],
                                           "Total": 1, "Limit": 10, "Offset": 0})
        _, first = self.query_file("ListCoupons", {}, "first")
        _, second = self.query_file("ListCoupons", {}, "second")
        envelope = json.loads(first.read_text())
        envelope["result"]["metadata"] = json.loads(second.read_text())["result"]["metadata"]
        first.write_text(json.dumps(envelope), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "来源不一致"):
            load_attribution_input(first, input_name="coupons")

    def test_empty_usage_query_proves_zero_only_for_the_queried_coupon(self) -> None:
        coupons = [{"CouponID": name, "Status": 1, "AmountLimit": 0, "PayTypeLimit": "post",
                    "BeginTime": "2026-01-01T00:00:00Z", "ExpiredTime": "2026-12-31T23:59:59Z",
                    "ProductLimitList": [{"ProductCode": "TOS", "ConfigurationType": 1,
                                          "ChargeItemType": 0}]}
                   for name in ("synthetic-queried", "synthetic-unqueried")]
        self.write_fixture("ListCoupons", {"List": coupons, "Total": 2, "Limit": 10, "Offset": 0})
        self.write_fixture("ListCouponUsageRecords", {"List": [], "Total": 0, "Limit": 10, "Offset": 0})
        _, inventory = self.query_file("ListCoupons", {}, "inventory")
        code, usage = self.query("ListCouponUsageRecords", {"CouponID": "synthetic-queried"},
                                 "--pagination", "full")
        self.assertEqual(0, code, usage)
        self.assertEqual([], usage["result"])
        usage_path = self.root / "usage.json"
        usage_path.write_text(json.dumps(usage), encoding="utf-8")
        self.assertEqual(("synthetic-queried",),
                         load_attribution_input(usage_path, input_name="usage").queried_coupon_ids)
        for period in ("2026-08", "2026-09"):
            self.write_fixture(f"ListBillDetail__period-{period}__offset-0", {
                "List": [{"BillPeriod": period, "Product": "TOS", "ConfigName": "storage",
                          "InstanceNo": "synthetic-bucket", "ElementCode": "storage",
                          "BillingMode": "2", "Currency": "CNY", "DiscountBillAmount": "10",
                          "CouponAmount": "0", "PayableAmount": "10"}],
                "Total": 1, "Limit": 300, "Offset": 0,
            })
        bills = self.root / "bills.csv"
        self.run_cli(["query", "--action", "ListBillDetail", "--body", '{"GroupPeriod":2,"GroupTerm":0}',
                      "--period", "2026-08", "--period", "2026-09", "--pagination", "full",
                      "--fixture-dir", str(self.root), "--out", str(bills)])
        result = self.run_cli(["coupon", "--coupons", str(inventory), "--usage-records", str(usage_path),
                               "--bill-details", str(bills), "--analysis-period", "2026-09",
                               "--comparison-period", "2026-08"])["result"]
        summaries = result["coupon_usage_summaries"]
        self.assertEqual(1, len(summaries))
        self.assertEqual("synthetic-queried", summaries[0]["coupon"]["CouponID"])
        self.assertEqual("0", summaries[0]["periods"]["2026-09"]["redeemed_amount"])
        self.assertTrue(any(item.get("coupon_id") == "synthetic-unqueried"
                            for item in result["insufficient_evidence"]))

    def test_current_period_project_and_nested_drill_inherit_parent_limits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            period = date.today().strftime("%Y-%m")
            common = {"Product": "ECS", "Currency": "CNY", "Element": "CPU"}
            left_rows = [{**common, "InstanceNo": "synthetic-one", "PayableAmount": "100"},
                         {**common, "InstanceNo": "synthetic-two", "PayableAmount": "40"}]
            right_rows = [{**common, "InstanceNo": "synthetic-one", "Project": "a", "PayableAmount": "60"},
                          {**common, "InstanceNo": "synthetic-one", "Project": "b", "PayableAmount": "40"},
                          {**common, "InstanceNo": "synthetic-two", "Project": "a", "PayableAmount": "40"}]
            sources = []
            for action, name, rows in (("ListBillDetail", "left", left_rows),
                                       ("ListSplitBillDetail", "right", right_rows)):
                (root / f"{action}.json").write_text(json.dumps({"Result": {
                    "List": rows, "Total": len(rows), "Limit": 300, "Offset": 0}}))
                body = {"BillPeriod": period, "GroupPeriod": 2}
                if action == "ListBillDetail":
                    body["GroupTerm"] = 0
                output = root / f"{name}.csv"
                self.run_cli(["query", "--action", action, "--body", json.dumps(body), "--pagination", "full",
                     "--fixture-dir", str(root), "--out", str(output)])
                sources.extend([output, output.with_suffix(".meta.json"), output.with_suffix(".fields.json")])
            before = {path: path.read_bytes() for path in sources}
            parent, child, grandchild = root / "parent.csv", root / "project.csv", root / "instances.csv"
            parent_result = self.run_cli(["reconcile", "run", "--left", str(root / "left.csv"),
                                 "--right", str(root / "right.csv"), "--group-by", "Product", "--out", str(parent)])
            child_result = self.run_cli(["reconcile", "drill-down", "--from", str(parent), "--row", "Product=ECS",
                                "--row", "Currency=CNY", "--by", "Project", "--side", "right", "--out", str(child)])
            grandchild_result = self.run_cli(["reconcile", "drill-down", "--from", str(child), "--row", "Product=ECS",
                                     "--row", "Currency=CNY", "--row", "Project=a", "--by", "InstanceNo",
                                     "--side", "right", "--out", str(grandchild)])
            parent_warnings = json.loads(parent.with_suffix(".meta.json").read_text())["warnings"]
            for path, payload in ((child, child_result), (grandchild, grandchild_result)):
                metadata = json.loads(path.with_suffix(".meta.json").read_text())
                self.assertEqual("provisional", payload["_meta"]["claim_scope"])
                self.assertEqual("provisional", metadata["claim_scope"])
                self.assertTrue(set(parent_warnings) <= set(metadata["warnings"]))
                self.assertEqual("matched", payload["_meta"]["conservation"]["status"])
                self.assertIn("当前", payload["message"])
            self.assertEqual("provisional", parent_result["_meta"]["claim_scope"])
            self.assertEqual(before, {path: path.read_bytes() for path in sources})


if __name__ == "__main__":
    unittest.main()
