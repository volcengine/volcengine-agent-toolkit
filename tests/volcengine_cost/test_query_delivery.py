"""Public CLI regressions for requested pages and nested field discovery."""

from __future__ import annotations

import contextlib
import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2] / "skills/core/volcengine-cost"
sys.path.insert(0, str(ROOT / "scripts"))

from cost import main  # noqa: E402
from cost_query.billing.client import FixtureBillingClient  # noqa: E402
from cost_query.billing.json_schema import schema_contract  # noqa: E402


class QueryDeliveryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.client = FixtureBillingClient(self.root)

    def write_fixture(self, name: str, result: dict) -> None:
        (self.root / f"{name}.json").write_text(json.dumps({"Result": result}), encoding="utf-8")

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


if __name__ == "__main__":
    unittest.main()
